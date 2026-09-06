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
    "Check & use provider",
    "Reject",
    "Re-score accepted changes",
  ]) {
    assert.match(page, new RegExp(expected.replace("&", "&")));
  }
});

test("profile lab states the human approval boundary", () => {
  assert.match(page, /You approve every word/);
  assert.match(page, /nothing is applied automatically/);
});
