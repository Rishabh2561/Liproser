from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

SECTIONS = {
    "headline": "Backend Engineer | Python | FastAPI",
    "about": "I build APIs and work with databases.",
    "experience": "Implemented an internal reporting service at ExampleCo from 2023 to 2024.",
    "skills": "Python, FastAPI, PostgreSQL",
    "featured": "Internal reporting service",
}


def test_v01_application_api_contract(client):
    paths = client.get("/openapi.json").json()["paths"]
    expected = {
        "/v1/setup",
        "/v1/setup/provider-check",
        "/v1/profile-imports",
        "/v1/profile-imports/{import_id}",
        "/v1/profile-imports/{import_id}/confirm",
        "/v1/profile-imports/{import_id}/source",
        "/v1/profiles/{profile_id}/analyses",
        "/v1/profile-suggestions/{suggestion_id}/decisions",
        "/v1/profiles/{profile_id}/rescore",
        "/v1/usage/ai-budget",
    }
    assert expected <= set(paths)


def text_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(
        b"BT /F1 12 Tf 72 720 Td (Headline) Tj 0 -18 Td "
        b"(Backend Engineer) Tj 0 -18 Td (About) Tj 0 -18 Td (I build APIs.) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_manual_profile_decision_and_rescore(client):
    imported = client.post("/v1/profile-imports", json={"kind": "MANUAL", "sections": SECTIONS})
    assert imported.status_code == 201
    import_id = imported.json()["id"]
    confirmed = client.post(
        f"/v1/profile-imports/{import_id}/confirm",
        json={
            "sections": SECTIONS,
            "target_role": "Senior Backend Engineer",
            "domain": "software engineering",
        },
    )
    profile_id = confirmed.json()["profile_id"]
    audit = client.post(f"/v1/profiles/{profile_id}/analyses")
    assert audit.status_code == 201
    payload = audit.json()
    assert payload["rubric_version"] == "profile-rubric@1"
    assert len(payload["suggestions"]) == 5
    experience = next(item for item in payload["suggestions"] if item["section"] == "experience")
    assert "ExampleCo" in experience["after"]
    assert "2023 to 2024" in experience["after"]
    assert experience["proposed_claims"] == []
    decision = client.post(
        f"/v1/profile-suggestions/{experience['id']}/decisions", json={"action": "ACCEPT"}
    )
    assert decision.status_code == 200
    duplicate = client.post(
        f"/v1/profile-suggestions/{experience['id']}/decisions", json={"action": "REJECT"}
    )
    assert duplicate.status_code == 409
    rescored = client.post(f"/v1/profiles/{profile_id}/rescore")
    assert rescored.status_code == 200
    assert rescored.json()["rubric_version"] == payload["rubric_version"]


def test_pdf_validation_and_retained_source_deletion(client):
    invalid = client.post(
        "/v1/profile-imports", files={"file": ("profile.pdf", b"not-pdf", "application/pdf")}
    )
    assert invalid.status_code == 422

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    stream = BytesIO()
    writer.write(stream)
    blank = client.post(
        "/v1/profile-imports", files={"file": ("profile.pdf", stream.getvalue(), "application/pdf")}
    )
    assert blank.status_code == 422

    valid = client.post(
        "/v1/profile-imports",
        files={"file": ("profile.pdf", text_pdf(), "application/pdf")},
    )
    assert valid.status_code == 201
    payload = valid.json()
    assert payload["source_retained"] is True
    assert "Backend Engineer" in payload["sections"]["headline"]
    source = client.get(f"/v1/profile-imports/{payload['id']}/source")
    assert source.status_code == 200
    deleted = client.delete(f"/v1/profile-imports/{payload['id']}/source")
    assert deleted.json()["confirmed_sections_retained"] is True
    assert client.get(f"/v1/profile-imports/{payload['id']}/source").status_code == 404


def test_pdf_with_active_content_is_rejected(client):
    payload = text_pdf().replace(b"%%EOF", b"/OpenAction /JavaScript\n%%EOF")
    response = client.post(
        "/v1/profile-imports",
        files={"file": ("active.pdf", payload, "application/pdf")},
    )
    assert response.status_code == 422
    assert "active content" in response.json()["detail"]


def test_setup_and_budget_never_expose_secrets(client):
    setup = client.get("/v1/setup")
    assert setup.status_code == 200
    assert setup.json()["provider"] == "unconfigured"
    assert setup.json()["secrets_exposed"] is False
    checked = client.post("/v1/setup/provider-check", json={"provider": "fake", "model": "fake-v1"})
    assert checked.json()["ready"] is True
    assert client.get("/v1/setup").json()["provider"] == "fake"
    budget = client.get("/v1/usage/ai-budget")
    assert budget.status_code == 200
    assert budget.json()["limit_usd"] == 10.0
    assert budget.json()["remaining_usd"] == 10.0
