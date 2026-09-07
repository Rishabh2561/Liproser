"use client";

import { FormEvent, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const empty = { headline: "", about: "", experience: "", skills: "", featured: "" };
const sectionLabels = { headline: "Headline", about: "About", experience: "Experience", skills: "Skills", featured: "Featured" };
const sectionGuidance = {
  headline: "[Target role] | [Core expertise] | [Outcome you help create]",
  about: "Who you help → the outcome → how you work → one verified proof point → your current goal",
  experience: "Role and company → dates → ownership → actions → verified result or scale",
  skills: "Primary skill → supporting skill → tools/platforms → domain knowledge",
  featured: "Project, article, or portfolio item → what it demonstrates or achieved",
};

type Sections = typeof empty;
type Suggestion = { id: string; section: string; before: string; after: string; rationale: string; confidence: number; decision?: string };
type PendingDecision = { suggestionId: string; action: "EDIT_AND_ACCEPT" | "REJECT"; text: string };
type Setup = { provider:string; model:string; provider_configured:boolean; credential_sources:Record<string,string> };
type Analysis = { total_score:number; rubric_version:string; suggestions:Suggestion[]; generation_provider:string; generation_model:string; generation_mode:"provider"|"deterministic_fallback"; generation_warning?:string|null };
type VoiceProfile = { id:string; version:number; domain:string; target_audience:string; content_pillars:string[]; tone_preferences:string[]; prohibited_phrases:string[]; taxonomy_version:string; samples:{id:string;text:string}[] };
type EvidenceDraft = { statement:string; source_url:string; freshness_date:string };
type ContentIdea = { id:string; taxonomy_version:string; pillar:string; topic:string; angle:string; audience_intent:string; evidence:{id:string;statement:string;source_url?:string|null;freshness_date?:string|null}[] };
type PrimaryDraft = { post_id:string; revision_id:string; state:"DRAFT"; hook:string; body:string; cta:string; content:string; pillar:string; topic:string; taxonomy_version:string; generation_model:string; generation_mode:"provider"|"deterministic_fallback"; generation_warning?:string|null; claims:{id:string;claim_text:string;kind:"SUPPORTED"|"OPINION";source_reference_ids:string[]}[] };

const splitList = (value: string) => value.split(/[,\n]/).map(item=>item.trim()).filter(Boolean);

export default function Home() {
  const [setup, setSetup] = useState<Setup | null>(null);
  const [provider, setProvider] = useState("fake");
  const [model, setModel] = useState("fake-v1");
  const [apiKey, setApiKey] = useState("");
  const [providerResult, setProviderResult] = useState<{ready:boolean;text:string} | null>(null);
  const [sections, setSections] = useState<Sections>(empty);
  const [importId, setImportId] = useState("");
  const [sourceRetained, setSourceRetained] = useState(false);
  const [profileId, setProfileId] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [domain, setDomain] = useState("");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [pendingDecision, setPendingDecision] = useState<PendingDecision | null>(null);
  const [message, setMessage] = useState("Ready for a private profile audit.");
  const [voiceDomain, setVoiceDomain] = useState("");
  const [voiceAudience, setVoiceAudience] = useState("");
  const [voicePillars, setVoicePillars] = useState("");
  const [voiceTones, setVoiceTones] = useState("");
  const [voiceAvoid, setVoiceAvoid] = useState("");
  const [voiceSamples, setVoiceSamples] = useState(["", "", ""]);
  const [voiceOwned, setVoiceOwned] = useState(false);
  const [voiceProfile, setVoiceProfile] = useState<VoiceProfile | null>(null);
  const [voiceMessage, setVoiceMessage] = useState("Configure your voice before generating content.");
  const [ideaPillar, setIdeaPillar] = useState("");
  const [ideaTopic, setIdeaTopic] = useState("");
  const [ideaAngle, setIdeaAngle] = useState("");
  const [ideaIntent, setIdeaIntent] = useState("");
  const [ideaEvidence, setIdeaEvidence] = useState<EvidenceDraft[]>([{statement:"",source_url:"",freshness_date:""}]);
  const [evidenceConfirmed, setEvidenceConfirmed] = useState(false);
  const [contentIdea, setContentIdea] = useState<ContentIdea | null>(null);
  const [primaryDraft, setPrimaryDraft] = useState<PrimaryDraft | null>(null);
  const [contentMessage, setContentMessage] = useState("Create one idea before generating its primary draft.");
  const filledSections = Object.values(sections).filter(value => value.trim()).length;
  const completeness = Math.round((filledSections / Object.keys(sections).length) * 100);

  useEffect(() => {
    fetch(`${API}/v1/setup`).then(response => response.json()).then((data: Setup) => {
      setSetup(data);
      if (data.provider !== "unconfigured") {
        setProvider(data.provider);
        setModel(data.model);
      }
    }).catch(() => setMessage("Start the API to continue."));
    fetch(`${API}/v1/voice-profiles/current`).then(async response => {
      if (!response.ok) return;
      const data: VoiceProfile = await response.json();
      setVoiceProfile(data);
      setVoiceDomain(data.domain);
      setVoiceAudience(data.target_audience);
      setVoicePillars(data.content_pillars.join(", "));
      setVoiceTones(data.tone_preferences.join(", "));
      setVoiceAvoid(data.prohibited_phrases.join(", "));
      setVoiceSamples(data.samples.map(sample=>sample.text));
      setVoiceOwned(true);
      setIdeaPillar(data.content_pillars[0] ?? "");
      setVoiceMessage(`Voice profile v${data.version} is ready.`);
    }).catch(()=>undefined);
  }, []);

  function chooseProvider(value: string) {
    const defaults: Record<string,string> = {fake:"fake-v1",ollama:"gemma3",openai:"gpt-5.6-luna",anthropic:""};
    setProvider(value);
    setModel(defaults[value] ?? "");
    setApiKey("");
    setProviderResult(null);
  }

  async function checkProvider() {
    setMessage("Checking the provider contract…");
    setProviderResult({ready:false,text:"Checking credentials, model access, and structured output…"});
    if ((provider === "openai" || provider === "anthropic") && apiKey.trim()) {
      const saved = await fetch(`${API}/v1/setup/provider-secret`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({provider,api_key:apiKey})});
      setApiKey("");
      if (!saved.ok) {
        setProviderResult({ready:false,text:"The session key could not be held by the local API."});
        return setMessage("Provider key setup failed.");
      }
    }
    const response = await fetch(`${API}/v1/setup/provider-check`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({provider,model})});
    const data = await response.json();
    setModel(data.model ?? model);
    setProviderResult({ready:Boolean(data.ready),text:data.detail ?? "Provider check failed."});
    setMessage(data.detail ?? "Provider check failed.");
    const refreshed = await fetch(`${API}/v1/setup`).then(result=>result.json());
    setSetup(refreshed);
  }

  async function clearProviderKey() {
    const response = await fetch(`${API}/v1/setup/provider-secret/${provider}`, {method:"DELETE"});
    if (!response.ok) return setProviderResult({ready:false,text:"The session key could not be cleared."});
    const refreshed = await fetch(`${API}/v1/setup`).then(result=>result.json());
    setSetup(refreshed);
    setProviderResult({ready:false,text:"Session key cleared. Environment keys, if present, are unchanged."});
  }

  async function importManual(event: FormEvent) {
    event.preventDefault();
    setMessage("Saving profile…");
    const response = await fetch(`${API}/v1/profile-imports`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({kind:"MANUAL",sections})});
    if (!response.ok) return setMessage("Could not save the profile.");
    const data = await response.json();
    setImportId(data.id);
    setSourceRetained(false);
    setMessage("Profile saved. Confirm the facts to continue.");
  }

  async function importPdf(file?: File) {
    if (!file) return;
    setMessage("Extracting the PDF…");
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(`${API}/v1/profile-imports`, {method:"POST",body:form});
    const data = await response.json();
    if (!response.ok) return setMessage(data.detail ?? "PDF import failed.");
    setSections(data.sections);
    setImportId(data.id);
    setSourceRetained(data.source_retained);
    setMessage("Review and correct the extracted sections before confirmation.");
  }

  async function deleteSource() {
    const response = await fetch(`${API}/v1/profile-imports/${importId}/source`, {method:"DELETE"});
    if (response.ok) { setSourceRetained(false); setMessage("The raw PDF was deleted; confirmed sections remain."); }
  }

  async function confirmAndAnalyze() {
    setMessage("Confirming facts and running your audit…");
    const confirmation = await fetch(`${API}/v1/profile-imports/${importId}/confirm`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({sections,target_role:targetRole,domain})});
    if (!confirmation.ok) return setMessage("Could not confirm this profile.");
    const confirmed = await confirmation.json();
    setProfileId(confirmed.profile_id);
    const response = await fetch(`${API}/v1/profiles/${confirmed.profile_id}/analyses`, {method:"POST"});
    if (!response.ok) return setMessage("The profile was saved, but the audit could not run.");
    setAnalysis(await response.json());
    setMessage("Audit complete. Review each suggestion—nothing is applied automatically.");
  }

  async function decide(item: Suggestion, action: "ACCEPT"|"EDIT_AND_ACCEPT"|"REJECT", text = "") {
    const edited = action === "EDIT_AND_ACCEPT" ? text.trim() : null;
    const reason = action === "REJECT" ? text.trim() : null;
    if (action !== "ACCEPT" && !text.trim()) return setMessage(action === "REJECT" ? "Add a rejection reason first." : "The edited suggestion cannot be empty.");
    const response = await fetch(`${API}/v1/profile-suggestions/${item.id}/decisions`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({action,edited_text:edited,reason})});
    if (!response.ok) return setMessage("That decision could not be recorded.");
    setPendingDecision(null);
    setAnalysis(current => current ? {...current,suggestions:current.suggestions.map(suggestion => suggestion.id === item.id ? {...suggestion,decision:action} : suggestion)} : current);
  }

  async function rescore() {
    const response = await fetch(`${API}/v1/profiles/${profileId}/rescore`, {method:"POST"});
    setAnalysis(await response.json());
    setMessage("Re-scored with the same rubric version.");
  }

  async function saveVoiceProfile(event: FormEvent) {
    event.preventDefault();
    const samples = voiceSamples.map(value=>value.trim()).filter(Boolean);
    if (samples.length < 3) return setVoiceMessage("Add at least three substantive samples you own.");
    if (!voiceOwned) return setVoiceMessage("Confirm that every sample is yours or authorized for this private use.");
    setVoiceMessage("Saving a new immutable voice-profile version…");
    const response = await fetch(`${API}/v1/voice-profiles`, {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        domain:voiceDomain,
        target_audience:voiceAudience,
        content_pillars:splitList(voicePillars),
        tone_preferences:splitList(voiceTones),
        prohibited_phrases:splitList(voiceAvoid),
        samples,
        samples_are_user_owned:voiceOwned,
      }),
    });
    if (!response.ok) return setVoiceMessage("Check the required fields: domain, audience, pillars, tone, and 3–5 distinct samples of at least 20 characters.");
    const data: VoiceProfile = await response.json();
    setVoiceProfile(data);
    setIdeaPillar(data.content_pillars[0] ?? "");
    setVoiceMessage(`Voice profile v${data.version} saved with ${data.taxonomy_version}.`);
  }

  async function saveContentIdea(event: FormEvent) {
    event.preventDefault();
    if (!voiceProfile) return setContentMessage("Save a voice profile first.");
    if (!evidenceConfirmed) return setContentMessage("Confirm that the supplied evidence is accurate.");
    setContentMessage("Saving one tagged idea and its evidence ledger…");
    const evidence = ideaEvidence.filter(item=>item.statement.trim()).map(item=>({
      statement:item.statement.trim(),
      source_url:item.source_url.trim() || null,
      freshness_date:item.freshness_date || null,
    }));
    const response = await fetch(`${API}/v1/content-ideas`, {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({pillar:ideaPillar,topic:ideaTopic,angle:ideaAngle,audience_intent:ideaIntent,format:"TEXT",evidence,evidence_confirmed:true}),
    });
    if (!response.ok) return setContentMessage("Check the pillar, topic, angle, audience intent, and evidence fields.");
    const data: ContentIdea = await response.json();
    setContentIdea(data);
    setPrimaryDraft(null);
    setContentMessage("Idea saved. Generate its single primary draft when ready.");
  }

  async function generatePrimaryDraft() {
    if (!contentIdea) return;
    setContentMessage("Generating one primary draft with evidence checks…");
    const response = await fetch(`${API}/v1/content-ideas/${contentIdea.id}/primary-draft`, {method:"POST"});
    const data = await response.json();
    if (!response.ok) return setContentMessage(data.detail ?? "The primary draft could not be generated.");
    setPrimaryDraft(data);
    setContentMessage("Primary draft ready. Review controls arrive in v0.2C; nothing is approved yet.");
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#top" aria-label="Liproser home"><span>Li</span><strong>Liproser</strong></a>
      <nav aria-label="Primary navigation">
        <a className="nav-item active" href="#profile"><span>01</span>Profile lab</a>
        <a className="nav-item" href="#voice"><span>02</span>Voice setup<small>v0.2</small></a>
        <span className="nav-item disabled"><span>03</span>Calendar<small>v0.3</small></span>
        <span className="nav-item disabled"><span>04</span>Analytics<small>v0.4</small></span>
      </nav>
      <div className="privacy-card"><span className="privacy-icon">✓</span><strong>Private by design</strong><p>Your profile remains on this machine. Nothing publishes automatically.</p></div>
      <p className="version">Personal edition · v0.1</p>
    </aside>

    <main className="workspace" id="top">
      <div className="topbar"><p>Good profiles are specific, credible, and easy to scan.</p><div className={`api-pill ${setup?.provider_configured ? "online" : ""}`}><span />{setup ? `${setup.provider} provider` : "API offline"}</div></div>

      <header className="hero">
        <div className="hero-copy">
          <div className="release-pill">Profile optimizer · Phase 1</div>
          <h1>Turn your experience into a profile people remember.</h1>
          <p>Import your LinkedIn profile and protect every verified fact. You approve every word and every change, section by section.</p>
          <div className="trust-row"><span>✓ Fact-preserving</span><span>✓ Human approved</span><span>✓ Local-first</span></div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="profile-preview"><div className="preview-head"><div className="avatar">R</div><div><i /><i /></div><b>+18</b></div><div className="preview-score"><span>Profile strength</span><strong>{analysis ? analysis.total_score : completeness}<small>/100</small></strong></div><div className="preview-bars"><i /><i /><i /><i /></div></div>
          <div className="floating-note"><span>↗</span><div><strong>Clearer positioning</strong><small>Without invented claims</small></div></div>
        </div>
      </header>

      <section className="journey" aria-label="Profile optimization steps">
        <div className={importId ? "done" : "current"}><span>1</span><p><strong>Import</strong><small>Add profile sections</small></p></div><i />
        <div className={profileId ? "done" : importId ? "current" : ""}><span>2</span><p><strong>Confirm</strong><small>Verify every fact</small></p></div><i />
        <div className={analysis ? "current" : ""}><span>3</span><p><strong>Optimize</strong><small>Review suggestions</small></p></div>
      </section>

      <section className="section-block" id="profile">
        <div className="section-heading"><div><p className="eyebrow">START HERE</p><h2>Choose how to bring in your profile</h2><p>Two private import methods are ready now. Official LinkedIn connection is shown separately because it requires approved API access.</p></div><div className="completion"><strong>{completeness}%</strong><span>profile supplied</span></div></div>
        <div className="import-options">
          <article className="import-option selected"><div className="option-icon">Aa</div><span className="available">Available now</span><h3>Paste profile sections</h3><p>Best when you want complete control over exactly what enters the audit.</p><a href="#manual-editor">Use manual editor <span>→</span></a></article>
          <label className="import-option pdf-option"><div className="option-icon">PDF</div><span className="available">Available now</span><h3>Import LinkedIn PDF</h3><p>Upload your official profile export, then verify the extracted sections.</p><strong>Choose PDF <span>↑</span></strong><input type="file" accept="application/pdf" aria-label="Import LinkedIn PDF" onChange={event=>importPdf(event.target.files?.[0])}/></label>
          <article className="import-option locked"><div className="option-icon">in</div><span className="gated">API-gated</span><h3>Connect LinkedIn</h3><p>Identity login alone cannot fetch your full profile, posts, or analytics.</p><button disabled aria-describedby="linkedin-boundary">Not available in v0.1</button></article>
        </div>
        <div className="linkedin-boundary" id="linkedin-boundary"><span>i</span><p><strong>Why isn’t profile login active?</strong> LinkedIn only provides full profile, post, analytics, and publishing data through separately approved capabilities. Liproser will enable each connection only after LinkedIn grants it—never through scraping or browser automation.</p></div>
      </section>

      <section className="provider-panel">
        <div className="provider-copy"><div className="provider-mark">✦</div><div><p className="eyebrow">AI ENGINE</p><h3>Choose your analysis provider</h3><p>Use a no-cost local model, an environment key, or a hosted key held only for this API session.</p></div></div>
        <label><span>Provider</span><select value={provider} onChange={event=>chooseProvider(event.target.value)} aria-label="AI provider"><option value="fake">Fake / no cost</option><option value="ollama">Ollama</option><option value="openai">OpenAI</option><option value="anthropic">Claude</option></select></label>
        <label><span>Model</span><input value={model} onChange={event=>setModel(event.target.value)} aria-label="Model identifier" placeholder="Model identifier"/></label>
        {(provider === "openai" || provider === "anthropic") && <label className="provider-secret"><span>API key · session only</span><input type="password" value={apiKey} onChange={event=>setApiKey(event.target.value)} aria-label={`${provider === "openai" ? "OpenAI" : "Claude"} API key (session only)`} placeholder={setup?.credential_sources?.[provider] === "missing" ? "Paste key for this session" : "Key already configured"} autoComplete="off" spellCheck={false}/></label>}
        <div className="provider-actions"><button className="button light" onClick={checkProvider}>Save & check provider</button>{setup?.credential_sources?.[provider] === "session" && <button className="clear-key" onClick={clearProviderKey}>Clear session key</button>}</div>
        {providerResult && <div className={`provider-result ${providerResult.ready ? "success" : "error"}`} role="alert"><span>{providerResult.ready ? "✓" : "i"}</span><p>{providerResult.text}</p></div>}
      </section>

      <form onSubmit={importManual} className="editor-card" id="manual-editor">
        <div className="editor-heading"><div><p className="eyebrow">MANUAL PROFILE</p><h2>Tell the complete story</h2><p>Paste only what is true today. You can correct extracted PDF text here too.</p></div><span>{filledSections}/5 sections</span></div>
        <div className="editor-grid">
          {(Object.keys(sections) as (keyof Sections)[]).map(key => <label className={`field field-${key}`} key={key}><span>{sectionLabels[key]} <small>{sections[key].trim() ? "Added" : "Empty"}</small></span><textarea aria-label={`${sectionLabels[key]} ${sections[key].trim() ? "Added" : "Empty"}`} value={sections[key]} onChange={event=>setSections({...sections,[key]:event.target.value})} rows={key === "headline" ? 2 : 5} placeholder={`Paste your ${key} section`} />{!sections[key].trim() && <div className="empty-guidance"><strong>Suggested structure</strong><span>{sectionGuidance[key]}</span><small>Replace prompts with facts you can verify.</small></div>}</label>)}
        </div>
        <div className="form-actions"><button className="button primary" type="submit">Save manual profile <span>→</span></button><p>Saved only to your private local database.</p></div>

        {importId && <div className="confirmation-panel">
          <div><span className="confirmation-check">✓</span><div><strong>Profile draft saved</strong><p>Add targeting context, confirm the facts, and run your first audit.</p></div></div>
          <div className="targeting"><label><span>Target role <small>Optional</small></span><input value={targetRole} onChange={event=>setTargetRole(event.target.value)} aria-label="Target role (optional)" placeholder="Senior Backend Engineer" /></label><label><span>Domain <small>Optional</small></span><input value={domain} onChange={event=>setDomain(event.target.value)} aria-label="Domain (optional)" placeholder="Software engineering" /></label></div>
          <button className="button accent" type="button" onClick={confirmAndAnalyze}>Confirm facts & run audit <span>✦</span></button>
        </div>}

        {sourceRetained && <div className="source-controls"><a className="button outline" href={`${API}/v1/profile-imports/${importId}/source`}>Download retained PDF</a><button className="button danger" type="button" onClick={deleteSource}>Delete retained PDF</button></div>}
      </form>

      <p className="message" role="status"><span />{message}</p>

      {analysis && <section className="results">
        <div className="results-heading"><div className="score-ring"><strong>{analysis.total_score}</strong><span>/ 100</span></div><div><p className="eyebrow">YOUR AUDIT · {analysis.rubric_version}</p><h2>Specific changes, under your control.</h2><p>Review the evidence and decide what sounds like you.</p><span className={`generation-badge ${analysis.generation_mode}`}>{analysis.generation_mode === "provider" ? `✦ AI rewrites · ${analysis.generation_model}` : "Safe deterministic fallback"}</span>{analysis.generation_warning && <p className="generation-warning">{analysis.generation_warning}</p>}</div></div>
        <div className="suggestions">{analysis.suggestions.map(item=><article key={item.id}>
          <div className="suggestion-head"><strong>{item.section}</strong><span>{item.before.trim() ? `${Math.round(item.confidence*100)}% confidence` : "Fill-in template"}</span></div>
          <div className="diff"><div><small>BEFORE</small><p>{item.before || "Empty"}</p></div><div className="after"><small>{item.before.trim() ? "PROPOSED" : "FILL-IN TEMPLATE"}</small><p>{item.after}</p></div></div>
          <p className="why"><span>Why</span>{item.rationale}</p>
          {!item.before.trim() && <p className="template-note">Replace every bracketed prompt with verified information before accepting.</p>}
          {item.decision ? <span className="decision">✓ {item.decision.replaceAll("_", " ")}</span> : <><div className="actions">{item.before.trim() && <button onClick={()=>decide(item,"ACCEPT")}>Accept</button>}<button onClick={()=>setPendingDecision({suggestionId:item.id,action:"EDIT_AND_ACCEPT",text:item.after})}>{item.before.trim() ? "Edit & accept" : "Fill template & accept"}</button><button onClick={()=>setPendingDecision({suggestionId:item.id,action:"REJECT",text:""})}>Reject</button></div>{pendingDecision?.suggestionId === item.id && <div className="decision-editor"><label><span>{pendingDecision.action === "REJECT" ? "Rejection reason" : "Edited suggestion"}</span><textarea aria-label={`${pendingDecision.action === "REJECT" ? "Rejection reason" : "Edited suggestion"} for ${item.section}`} value={pendingDecision.text} onChange={event=>setPendingDecision({...pendingDecision,text:event.target.value})} rows={4}/></label><div className="actions"><button className="button primary" onClick={()=>decide(item,pendingDecision.action,pendingDecision.text)}>{pendingDecision.action === "REJECT" ? "Save rejection" : "Save edited suggestion"}</button><button onClick={()=>setPendingDecision(null)}>Cancel</button></div></div>}</>}
        </article>)}</div>
        <button className="button primary rescore" onClick={rescore}>Re-score accepted changes <span>↗</span></button>
      </section>}

      <section className="voice-section" id="voice">
        <div className="voice-heading"><div><p className="eyebrow">CONTENT STUDIO · v0.2A</p><h2>Teach Liproser how you sound.</h2><p>Define your domain, audience, boundaries, and examples before any post is generated. Samples stay private and must be your own or authorized.</p></div>{voiceProfile && <div className="voice-version"><strong>v{voiceProfile.version}</strong><span>{voiceProfile.taxonomy_version}</span></div>}</div>
        <form onSubmit={saveVoiceProfile} className="voice-form">
          <div className="voice-grid">
            <label><span>Domain</span><input aria-label="Voice domain" value={voiceDomain} onChange={event=>setVoiceDomain(event.target.value)} placeholder="Software engineering" required /></label>
            <label><span>Target audience</span><input aria-label="Target audience" value={voiceAudience} onChange={event=>setVoiceAudience(event.target.value)} placeholder="Backend engineers and engineering leaders" required /></label>
            <label><span>Content pillars <small>comma separated</small></span><input aria-label="Content pillars" value={voicePillars} onChange={event=>setVoicePillars(event.target.value)} placeholder="API design, career growth, engineering leadership" required /></label>
            <label><span>Tone preferences <small>comma separated</small></span><input aria-label="Tone preferences" value={voiceTones} onChange={event=>setVoiceTones(event.target.value)} placeholder="Practical, clear, thoughtful" required /></label>
            <label className="voice-wide"><span>Phrases to avoid <small>optional</small></span><input aria-label="Phrases to avoid" value={voiceAvoid} onChange={event=>setVoiceAvoid(event.target.value)} placeholder="Game changer, unlock your potential" /></label>
          </div>
          <div className="sample-heading"><div><strong>Your writing samples</strong><p>Add 3–5 posts you wrote. They establish style only; they are not published or shared.</p></div>{voiceSamples.length < 5 && <button type="button" onClick={()=>setVoiceSamples([...voiceSamples,""])}>+ Add sample</button>}</div>
          <div className="voice-samples">{voiceSamples.map((sample,index)=><label key={index}><span>Sample {index+1}{voiceSamples.length > 3 && <button type="button" aria-label={`Remove sample ${index+1}`} onClick={()=>setVoiceSamples(voiceSamples.filter((_,position)=>position!==index))}>Remove</button>}</span><textarea aria-label={`Voice sample ${index+1}`} value={sample} onChange={event=>setVoiceSamples(voiceSamples.map((value,position)=>position===index?event.target.value:value))} rows={5} placeholder="Paste a post you wrote (minimum 20 characters)" /></label>)}</div>
          <label className="ownership-check"><input type="checkbox" checked={voiceOwned} onChange={event=>setVoiceOwned(event.target.checked)} /><span>I confirm these samples are mine or I am authorized to use them privately.</span></label>
          <div className="voice-actions"><button className="button primary" type="submit">Save voice profile</button><p role="status">{voiceMessage}</p></div>
          {voiceProfile && <div className="taxonomy-preview"><strong>Controlled taxonomy</strong><span>Domain · {voiceProfile.domain}</span>{voiceProfile.content_pillars.map(pillar=><span key={pillar}>Pillar · {pillar}</span>)}</div>}
        </form>
      </section>

      <section className="content-studio" id="create">
        <div className="studio-heading"><div><p className="eyebrow">CONTENT STUDIO · v0.2B</p><h2>Turn one idea into one grounded draft.</h2><p>Choose a controlled pillar, state the intended takeaway, and attach only evidence you have confirmed. Liproser creates no variants unless you ask in a later review step.</p></div><span className="draft-limit">1 idea → 1 primary draft</span></div>
        {!voiceProfile ? <div className="studio-locked"><strong>Voice setup required</strong><p>Save the v0.2A voice profile above before creating content.</p></div> : <>
          <form className="idea-form" onSubmit={saveContentIdea}>
            <div className="idea-grid">
              <label><span>Content pillar</span><select aria-label="Idea content pillar" value={ideaPillar} onChange={event=>setIdeaPillar(event.target.value)}>{voiceProfile.content_pillars.map(pillar=><option key={pillar}>{pillar}</option>)}</select></label>
              <label><span>Post topic</span><input aria-label="Post topic" value={ideaTopic} onChange={event=>setIdeaTopic(event.target.value)} placeholder="Designing explicit retry contracts" required /></label>
              <label className="idea-wide"><span>Core angle or takeaway</span><textarea aria-label="Core angle or takeaway" value={ideaAngle} onChange={event=>setIdeaAngle(event.target.value)} rows={3} placeholder="What should the reader understand or do differently?" required /></label>
              <label className="idea-wide"><span>Audience intent</span><input aria-label="Audience intent" value={ideaIntent} onChange={event=>setIdeaIntent(event.target.value)} placeholder="Help backend engineers review retry behavior before deployment" required /></label>
            </div>
            <div className="evidence-heading"><div><strong>Evidence ledger</strong><p>Optional facts, one record at a time. Sources add traceability; public text is never used as a voice sample.</p></div>{ideaEvidence.length < 5 && <button type="button" onClick={()=>setIdeaEvidence([...ideaEvidence,{statement:"",source_url:"",freshness_date:""}])}>+ Add evidence</button>}</div>
            <div className="evidence-list">{ideaEvidence.map((item,index)=><div className="evidence-row" key={index}>
              <label><span>Confirmed statement {index+1}</span><textarea aria-label={`Evidence statement ${index+1}`} value={item.statement} onChange={event=>setIdeaEvidence(ideaEvidence.map((value,position)=>position===index?{...value,statement:event.target.value}:value))} rows={2} placeholder="Paste the exact fact or result you can support" /></label>
              <label><span>Source URL <small>optional</small></span><input aria-label={`Evidence source URL ${index+1}`} value={item.source_url} onChange={event=>setIdeaEvidence(ideaEvidence.map((value,position)=>position===index?{...value,source_url:event.target.value}:value))} placeholder="https://…" /></label>
              <label><span>Freshness date <small>optional</small></span><input type="date" aria-label={`Evidence freshness date ${index+1}`} value={item.freshness_date} onChange={event=>setIdeaEvidence(ideaEvidence.map((value,position)=>position===index?{...value,freshness_date:event.target.value}:value))} /></label>
              {ideaEvidence.length > 1 && <button type="button" aria-label={`Remove evidence ${index+1}`} onClick={()=>setIdeaEvidence(ideaEvidence.filter((_,position)=>position!==index))}>Remove</button>}
            </div>)}</div>
            <label className="evidence-check"><input type="checkbox" checked={evidenceConfirmed} onChange={event=>setEvidenceConfirmed(event.target.checked)} /><span>I confirm the evidence and topic details are accurate. Unsupported claims must not be generated.</span></label>
            <div className="studio-actions"><button className="button primary" type="submit">Save one content idea</button><p role="status">{contentMessage}</p></div>
          </form>
          {contentIdea && <article className="idea-card"><div><span>{contentIdea.taxonomy_version}</span><span>{contentIdea.pillar}</span><span>Text</span></div><h3>{contentIdea.topic}</h3><p>{contentIdea.angle}</p><small>{contentIdea.evidence.length} confirmed evidence record{contentIdea.evidence.length === 1 ? "" : "s"}</small>{!primaryDraft && <button className="button accent" onClick={generatePrimaryDraft}>Generate primary draft ✦</button>}</article>}
          {primaryDraft && <div className="draft-workspace">
            <div className="draft-meta"><div><span>DRAFT · REVISION 1</span><strong>{primaryDraft.pillar}</strong></div><div><span>{primaryDraft.generation_mode === "provider" ? `AI · ${primaryDraft.generation_model}` : "Safe fallback"}</span><strong>Not approved</strong></div></div>
            {primaryDraft.generation_warning && <p className="draft-warning">{primaryDraft.generation_warning}</p>}
            <article className="linkedin-preview" aria-label="LinkedIn-style draft preview"><div className="preview-author"><span>R</span><div><strong>Your name</strong><small>Your headline · now</small></div><b>•••</b></div><p className="preview-content"><strong>{primaryDraft.hook}</strong>{`\n\n${primaryDraft.body}\n\n${primaryDraft.cta}`}</p><div className="preview-reactions"><span>○ ○</span><span>0 comments · 0 reposts</span></div></article>
            <div className="claim-ledger"><div><strong>Claim ledger</strong><span>{primaryDraft.claims.length} classified</span></div>{primaryDraft.claims.map(claim=><p key={claim.id}><span className={claim.kind.toLowerCase()}>{claim.kind}</span>{claim.claim_text}<small>{claim.source_reference_ids.length ? `${claim.source_reference_ids.length} evidence link` : "No factual source claimed"}</small></p>)}</div>
            <p className="review-boundary">This revision remains DRAFT. Review, edit, regenerate, reject, and approve controls arrive in v0.2C.</p>
          </div>}
        </>}
      </section>

      <footer><strong>Liproser</strong><span>Evidence over exaggeration.</span><small>Personal edition · v0.2 in progress · Data stays local</small></footer>
    </main>
  </div>;
}
