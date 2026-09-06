"use client";

import { FormEvent, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const empty = { headline: "", about: "", experience: "", skills: "", featured: "" };
type Sections = typeof empty;
type Suggestion = { id: string; section: string; before: string; after: string; rationale: string; confidence: number; decision?: string };
type PendingDecision = { suggestionId: string; action: "EDIT_AND_ACCEPT" | "REJECT"; text: string };

export default function Home() {
  const [setup, setSetup] = useState<{provider:string; provider_configured:boolean} | null>(null);
  const [provider, setProvider] = useState("fake");
  const [model, setModel] = useState("fake-v1");
  const [sections, setSections] = useState<Sections>(empty);
  const [importId, setImportId] = useState("");
  const [sourceRetained, setSourceRetained] = useState(false);
  const [profileId, setProfileId] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [domain, setDomain] = useState("");
  const [analysis, setAnalysis] = useState<{total_score:number; rubric_version:string; suggestions:Suggestion[]} | null>(null);
  const [pendingDecision, setPendingDecision] = useState<PendingDecision | null>(null);
  const [message, setMessage] = useState("Ready for a private profile audit.");

  useEffect(() => { fetch(`${API}/v1/setup`).then(r => r.json()).then(setSetup).catch(() => setMessage("Start the API to continue.")); }, []);

  async function checkProvider() {
    setMessage("Checking the provider contract…");
    const response = await fetch(`${API}/v1/setup/provider-check`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({provider,model})});
    const data = await response.json();
    setMessage(data.detail ?? "Provider check failed.");
    if (data.ready) setSetup({provider:data.provider, provider_configured:true});
  }

  async function importManual(event: FormEvent) {
    event.preventDefault(); setMessage("Saving profile…");
    const response = await fetch(`${API}/v1/profile-imports`, { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({kind:"MANUAL", sections}) });
    if (!response.ok) return setMessage("Could not save the profile.");
    const data = await response.json(); setImportId(data.id); setSourceRetained(false); setMessage("Profile saved. Confirm the facts to continue.");
  }

  async function importPdf(file?: File) {
    if (!file) return; setMessage("Extracting the PDF…");
    const form = new FormData(); form.append("file", file);
    const response = await fetch(`${API}/v1/profile-imports`, {method:"POST", body:form});
    const data = await response.json();
    if (!response.ok) return setMessage(data.detail ?? "PDF import failed.");
    setSections(data.sections); setImportId(data.id); setSourceRetained(data.source_retained); setMessage("Review and correct the extracted sections before confirmation.");
  }

  async function deleteSource() {
    const response = await fetch(`${API}/v1/profile-imports/${importId}/source`, {method:"DELETE"});
    if (response.ok) { setSourceRetained(false); setMessage("The raw PDF was deleted; confirmed sections remain."); }
  }

  async function confirmAndAnalyze() {
    const confirmation = await fetch(`${API}/v1/profile-imports/${importId}/confirm`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({sections,target_role:targetRole,domain})});
    const confirmed = await confirmation.json(); setProfileId(confirmed.profile_id);
    const response = await fetch(`${API}/v1/profiles/${confirmed.profile_id}/analyses`, {method:"POST"});
    setAnalysis(await response.json()); setMessage("Audit complete. Review each suggestion—nothing is applied automatically.");
  }

  async function decide(item: Suggestion, action: "ACCEPT"|"EDIT_AND_ACCEPT"|"REJECT", text = "") {
    const edited = action === "EDIT_AND_ACCEPT" ? text.trim() : null;
    const reason = action === "REJECT" ? text.trim() : null;
    if (action !== "ACCEPT" && !text.trim()) return setMessage(action === "REJECT" ? "Add a rejection reason first." : "The edited suggestion cannot be empty.");
    const response = await fetch(`${API}/v1/profile-suggestions/${item.id}/decisions`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({action,edited_text:edited,reason})});
    if (!response.ok) return setMessage("That decision could not be recorded.");
    setPendingDecision(null);
    setAnalysis(current => current ? {...current, suggestions: current.suggestions.map(s => s.id === item.id ? {...s, decision:action} : s)} : current);
  }

  async function rescore() {
    const response = await fetch(`${API}/v1/profiles/${profileId}/rescore`, {method:"POST"}); setAnalysis(await response.json()); setMessage("Re-scored with the same rubric version.");
  }

  return <main>
    <header><div className="mark">L</div><div><p className="eyebrow">PERSONAL PROFILE LAB</p><h1>Make your experience easier to see.</h1><p className="lede">A fact-preserving LinkedIn profile audit. You approve every word.</p></div><div className={`status ${setup?.provider_configured ? "ready" : ""}`}>{setup ? `${setup.provider} provider` : "API offline"}</div></header>
    <section className="provider-panel"><div><p className="eyebrow">FIRST-RUN SETUP</p><strong>Choose an AI provider</strong><p>Keys stay in your ignored local environment. Fake mode is safe for a no-cost walkthrough.</p></div><select value={provider} onChange={e=>setProvider(e.target.value)} aria-label="AI provider"><option value="fake">Fake / no cost</option><option value="ollama">Ollama</option><option value="openai">OpenAI</option><option value="anthropic">Claude</option></select><input value={model} onChange={e=>setModel(e.target.value)} aria-label="Model identifier" placeholder="Model identifier"/><button className="secondary" onClick={checkProvider}>Check & use provider</button></section>
    <section className="panel intro"><div><span className="step">01</span><h2>Bring in your profile</h2><p>Paste sections below or choose your LinkedIn PDF. Files stay in your private local storage until you delete them.</p></div><label className="upload">Import LinkedIn PDF<input type="file" accept="application/pdf" onChange={e=>importPdf(e.target.files?.[0])}/></label></section>
    <form onSubmit={importManual} className="editor">
      {(Object.keys(sections) as (keyof Sections)[]).map((key) => <label key={key}><span>{key}</span><textarea value={sections[key]} onChange={e=>setSections({...sections,[key]:e.target.value})} rows={key === "headline" ? 2 : 5} placeholder={`Paste your ${key} section`} /></label>)}
      <button className="primary" type="submit">Save manual profile</button>
      {importId && <><div className="targeting"><label><span>Target role (optional)</span><input value={targetRole} onChange={e=>setTargetRole(e.target.value)} placeholder="Senior Backend Engineer" /></label><label><span>Domain (optional)</span><input value={domain} onChange={e=>setDomain(e.target.value)} placeholder="Software engineering" /></label></div><button className="secondary" type="button" onClick={confirmAndAnalyze}>Confirm facts & run audit</button></>}
      {sourceRetained && <><a className="source-action" href={`${API}/v1/profile-imports/${importId}/source`}>Download retained PDF</a><button className="danger" type="button" onClick={deleteSource}>Delete retained PDF</button></>}
    </form>
    <p className="message" role="status">{message}</p>
    {analysis && <section className="results"><div className="score"><span>{analysis.total_score}</span><small>/ 100<br/>{analysis.rubric_version}</small></div><div><p className="eyebrow">YOUR AUDIT</p><h2>Specific changes, under your control.</h2></div>{analysis.suggestions.map(item=><article key={item.id}><div className="suggestion-head"><strong>{item.section}</strong><span>{Math.round(item.confidence*100)}% confidence</span></div><div className="diff"><div><small>BEFORE</small><p>{item.before || "Empty"}</p></div><div className="after"><small>PROPOSED</small><p>{item.after}</p></div></div><p className="why">{item.rationale}</p>{item.decision ? <span className="decision">{item.decision}</span> : <><div className="actions"><button onClick={()=>decide(item,"ACCEPT")}>Accept</button><button onClick={()=>setPendingDecision({suggestionId:item.id,action:"EDIT_AND_ACCEPT",text:item.after})}>Edit & accept</button><button onClick={()=>setPendingDecision({suggestionId:item.id,action:"REJECT",text:""})}>Reject</button></div>{pendingDecision?.suggestionId === item.id && <div className="decision-editor"><label><span>{pendingDecision.action === "REJECT" ? "Rejection reason" : "Edited suggestion"}</span><textarea aria-label={`${pendingDecision.action === "REJECT" ? "Rejection reason" : "Edited suggestion"} for ${item.section}`} value={pendingDecision.text} onChange={e=>setPendingDecision({...pendingDecision,text:e.target.value})} rows={4}/></label><div className="actions"><button className="primary" onClick={()=>decide(item,pendingDecision.action,pendingDecision.text)}>{pendingDecision.action === "REJECT" ? "Save rejection" : "Save edited suggestion"}</button><button onClick={()=>setPendingDecision(null)}>Cancel</button></div></div>}</>}</article>)}<button className="primary" onClick={rescore}>Re-score accepted changes</button></section>}
  </main>;
}
