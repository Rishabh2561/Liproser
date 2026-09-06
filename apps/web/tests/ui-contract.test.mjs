import { readFile } from "node:fs/promises";
import test from "node:test";
import assert from "node:assert/strict";

const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

test("profile lab exposes manual, PDF, decisions, and re-score actions", () => {
  for (const expected of [
    "Save manual profile",
    "Import LinkedIn PDF",
    "Confirm facts & run audit",
    "Edit & accept",
    "Delete retained PDF",
    "Save & check provider",
    "Reject",
    "Re-score accepted changes",
  ]) {
    assert.match(page, new RegExp(expected.replace("&", "&")));
  }
});

test("LinkedIn connection is visible without overstating available access", () => {
  assert.match(page, /Connect LinkedIn/);
  assert.match(page, /Not available in v0\.1/);
  assert.match(page, /Identity login alone cannot fetch your full profile, posts, or analytics/);
  assert.match(page, /never through scraping or browser automation/);
});

test("profile lab states the human approval boundary", () => {
  assert.match(page, /You approve every word/);
  assert.match(page, /nothing is applied automatically/);
});

test("audit targeting and review feedback use persistent inline controls", () => {
  assert.match(page, /Target role \(optional\)/);
  assert.match(page, /Domain \(optional\)/);
  assert.match(page, /Save edited suggestion/);
  assert.match(page, /Save rejection/);
  assert.doesNotMatch(page, /window\.prompt/);
});

test("hosted AI setup uses a masked session-only key and reports generation provenance", () => {
  assert.match(page, /type="password"/);
  assert.match(page, /API key · session only/);
  assert.match(page, /Clear session key/);
  assert.match(page, /generation_mode/);
  assert.doesNotMatch(page, /localStorage/);
});

test("empty profile sections receive guidance without directly accepting placeholders", () => {
  assert.match(page, /Suggested structure/);
  assert.match(page, /Replace prompts with facts you can verify/);
  assert.match(page, /FILL-IN TEMPLATE/);
  assert.match(page, /Fill template & accept/);
});
