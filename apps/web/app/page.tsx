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
type ReviewCategory = "HOOK"|"TONE"|"CLARITY"|"CTA"|"LENGTH"|"EVIDENCE";
type PrimaryDraft = { post_id:string; revision_id:string; revision_number:number; state:"DRAFT"|"IN_REVIEW"|"CHANGES_REQUESTED"|"REJECTED"|"APPROVED"|"SCHEDULED"|"PUBLISH_ACTION_REQUIRED"|"PUBLISHED"|"FAILED"; hook:string; body:string; cta:string; content:string; pillar:string; topic:string; taxonomy_version:string; generation_model:string; generation_mode:"provider"|"deterministic_fallback"|"human_edit"; generation_warning?:string|null; retrievals:{revision_id:string;topic:string;pillar:string;similarity_score:number;embedding_version:string;features:Record<string,string|number>}[]; claims:{id:string;claim_text:string;kind:"SUPPORTED"|"OPINION"|"CONFIRMED_PERSONAL";source_reference_ids:string[]}[]; checks:{id:string;check_type:string;severity:"BLOCKING"|"WARNING";passed:boolean;message:string}[]; reviews:{id:string;revision_id:string;revision_number:number;action:string;reason?:string|null;categories:string[];created_at:string}[] };
type MemoryRevision = { revision_id:string; post_id:string; state:string; revision_number:number; pillar:string; topic:string; taxonomy_version:string; embedding_version:string; features:{hook_style:string;word_count:number;paragraph_count:number;cta_style:string}; approved_at:string };
type CalendarSlot = {id:string;position:number;pillar:string;intended_local_at:string;resolved_utc_at:string;status:"PLANNED"|"ASSIGNED"|"CANCELLED"};
type ContentCalendar = {id:string;start_date:string;weeks:number;cadence_per_week:number;timezone:string;quiet_days:string[];slots:CalendarSlot[]};
type PostSchedule = {id:string;post_id:string;revision_id:string;calendar_slot_id?:string|null;timezone:string;intended_local_at:string;resolved_utc_at:string;status:"ACTIVE"|"REMINDER_DUE"|"COMPLETED"|"CANCELLED"|"FAILED"};
type PublishAction = {id:string;schedule_id:string;post_id:string;revision_id:string;state:"ACTION_REQUIRED"|"PUBLISHED"|"FAILED";formatted_content:string;published_url?:string|null};
type Preference = {id:string;category:string;instruction:string;evidence_count:number;active:boolean;version:number};
type Experiment = {id:string;name:string;hypothesis:string;variable:string;status:"ACTIVE"|"COMPLETED"};
type AnalyticsSummary = {snapshot_count:number;comparable_post_count:number;baseline_engagement_rate?:number|null;current_engagement_rate?:number|null;lift_percent?:number|null;best_pillars:{pillar:string;engagement_rate:number;post_count:number}[];calibration_count:number;mean_absolute_error?:number|null};
type Prediction = {id:string;post_revision_id:string;target_window_hours:number;basis:"DOMAIN_PRIOR"|"BLENDED"|"PERSONALIZED";bucket:"LOW"|"MEDIUM"|"HIGH";expected_engagement_rate:number;interval:[number,number];factors:{feature:string;impact:string;explanation:string}[];recommended_change?:string|null;limitations:string[];actual_engagement_rate?:number|null;absolute_error?:number|null};

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
  const [showDraftEditor, setShowDraftEditor] = useState(false);
  const [editedDraft, setEditedDraft] = useState({hook:"",body:"",cta:""});
  const [editClaimsConfirmed, setEditClaimsConfirmed] = useState(false);
  const [approvalConfirmed, setApprovalConfirmed] = useState(false);
  const [reviewFeedback, setReviewFeedback] = useState("");
  const [reviewCategories, setReviewCategories] = useState<ReviewCategory[]>([]);
  const [rejectionReason, setRejectionReason] = useState("");
  const [memoryRevisions, setMemoryRevisions] = useState<MemoryRevision[]>([]);
  const [calendar, setCalendar] = useState<ContentCalendar|null>(null);
  const [calendarStart, setCalendarStart] = useState(()=>new Date(Date.now()+86400000).toISOString().slice(0,10));
  const [calendarWeeks, setCalendarWeeks] = useState(4);
  const [calendarCadence, setCalendarCadence] = useState(3);
  const [calendarTimezone, setCalendarTimezone] = useState(()=>Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  const [calendarMessage, setCalendarMessage] = useState("Plan a balanced calendar, then assign an approved revision.");
  const [schedules, setSchedules] = useState<PostSchedule[]>([]);
  const [publishAction, setPublishAction] = useState<PublishAction|null>(null);
  const [publishedUrl, setPublishedUrl] = useState("");
  const [preferences, setPreferences] = useState<Preference[]>([]);
  const [analyticsRevisionId, setAnalyticsRevisionId] = useState("");
  const [predictionRevisionId, setPredictionRevisionId] = useState("");
  const [analyticsWindow, setAnalyticsWindow] = useState(168);
  const [analyticsSummary, setAnalyticsSummary] = useState<AnalyticsSummary|null>(null);
  const [prediction, setPrediction] = useState<Prediction|null>(null);
  const [analyticsMessage, setAnalyticsMessage] = useState("Import a published post or select one from your private library.");
  const [metricObserved, setMetricObserved] = useState(()=>new Date().toISOString().slice(0,16));
  const [metrics, setMetrics] = useState({impressions:"",reactions:"",comments:"",reposts:"",follower_delta:"",clicks:""});
  const [metricBaseline, setMetricBaseline] = useState(false);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [experimentId, setExperimentId] = useState("");
  const [experimentDraft, setExperimentDraft] = useState({name:"",hypothesis:"",variable:""});
  const [historical, setHistorical] = useState({pillar:"",topic:"",hook:"",body:"",cta:"",published_at:new Date(Date.now()-86400000).toISOString().slice(0,16)});
  const [historicalOwned, setHistoricalOwned] = useState(false);
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
      setHistorical(current=>({...current,pillar:current.pillar||data.content_pillars[0]||""}));
      setVoiceMessage(`Voice profile v${data.version} is ready.`);
    }).catch(()=>undefined);
    refreshMemory();
    refreshCalendar();
    refreshAnalytics();
  }, []);

  async function refreshMemory() {
    const response = await fetch(`${API}/v1/memory/revisions`).catch(()=>null);
    if (response?.ok) { const items=await response.json(); setMemoryRevisions(items); setAnalyticsRevisionId(current=>current||items.find((item:MemoryRevision)=>item.state==="PUBLISHED")?.revision_id||""); setPredictionRevisionId(current=>current||items[0]?.revision_id||""); }
  }

  async function refreshCalendar() {
    const [calendarResponse,scheduleResponse,actionResponse,preferenceResponse] = await Promise.all([
      fetch(`${API}/v1/calendars/current`).catch(()=>null),fetch(`${API}/v1/schedules`).catch(()=>null),fetch(`${API}/v1/publish-actions`).catch(()=>null),fetch(`${API}/v1/feedback/preferences`).catch(()=>null),
    ]);
    if (calendarResponse?.ok) setCalendar(await calendarResponse.json());
    if (scheduleResponse?.ok) setSchedules(await scheduleResponse.json());
    if (actionResponse?.ok) { const items=await actionResponse.json(); setPublishAction(items[0]??null); }
    if (preferenceResponse?.ok) setPreferences(await preferenceResponse.json());
  }

  async function planCalendar(event:FormEvent) {
    event.preventDefault();
    if (!voiceProfile) return setCalendarMessage("Save your voice profile before planning.");
    const response=await fetch(`${API}/v1/calendars`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({start_date:calendarStart,weeks:calendarWeeks,cadence_per_week:calendarCadence,timezone:calendarTimezone,quiet_days:["SATURDAY","SUNDAY"]})});
    const data=await response.json();
    if (!response.ok) return setCalendarMessage(data.detail??"Calendar could not be created.");
    setCalendar(data); setCalendarMessage(`${data.slots.length} balanced slots created. Weekends remain quiet.`);
  }

  async function scheduleApproved(slot:CalendarSlot) {
    if (!primaryDraft || primaryDraft.state!=="APPROVED") return setCalendarMessage("Approve the exact current revision first.");
    const response=await fetch(`${API}/v1/posts/${primaryDraft.post_id}/schedules`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision_id:primaryDraft.revision_id,intended_local_at:slot.intended_local_at,timezone:calendar?.timezone,calendar_slot_id:slot.id,idempotency_key:`slot-${slot.id}-${primaryDraft.revision_id}`})});
    const data=await response.json();
    if (!response.ok) return setCalendarMessage(data.detail??"The revision could not be scheduled.");
    setSchedules(current=>[...current.filter(item=>item.id!==data.id),data]); setCalendar(current=>current?{...current,slots:current.slots.map(item=>item.id===slot.id?{...item,status:"ASSIGNED"}:item)}:current); setPrimaryDraft({...primaryDraft,state:"SCHEDULED"}); setCalendarMessage("Exact approved revision scheduled. Editing it will cancel this schedule.");
  }

  async function preparePublish(item:PostSchedule) {
    const response=await fetch(`${API}/v1/schedules/${item.id}/publish-now`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision_id:item.revision_id,idempotency_key:`publish-${item.id}`})});
    const data=await response.json(); if(!response.ok)return setCalendarMessage(data.detail??"Publish action could not be prepared.");
    setPublishAction(data); if(primaryDraft)setPrimaryDraft({...primaryDraft,state:"PUBLISH_ACTION_REQUIRED"}); setCalendarMessage("Copy the formatted post, publish it yourself, then confirm below.");
  }

  async function confirmPublished() {
    if(!publishAction)return;
    const response=await fetch(`${API}/v1/publish-actions/${publishAction.id}/confirm`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({published_url:publishedUrl.trim()||null})});
    const data=await response.json(); if(!response.ok)return setCalendarMessage(data.detail??"Publication could not be confirmed.");
    setPublishAction(data); if(primaryDraft){setPrimaryDraft({...primaryDraft,state:"PUBLISHED"});setAnalyticsRevisionId(primaryDraft.revision_id);setPredictionRevisionId(primaryDraft.revision_id);} await refreshMemory(); setCalendarMessage("Publication confirmed. Add a comparable analytics snapshot below.");
  }

  async function togglePreference(item:Preference) {
    const response=await fetch(`${API}/v1/feedback/preferences/${item.id}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({active:!item.active})});
    if(response.ok){const updated=await response.json();setPreferences(current=>current.map(value=>value.id===updated.id?updated:value));}
  }

  async function refreshAnalytics(windowHours=analyticsWindow) {
    const [summaryResponse,predictionResponse,experimentResponse]=await Promise.all([
      fetch(`${API}/v1/analytics/summary?window_hours=${windowHours}`).catch(()=>null),
      fetch(`${API}/v1/predictions`).catch(()=>null),
      fetch(`${API}/v1/experiments`).catch(()=>null),
    ]);
    if(summaryResponse?.ok)setAnalyticsSummary(await summaryResponse.json());
    if(predictionResponse?.ok){const items=await predictionResponse.json();setPrediction(items[0]??null);}
    if(experimentResponse?.ok)setExperiments(await experimentResponse.json());
  }

  async function importHistoricalPost(event:FormEvent) {
    event.preventDefault();
    if(!historicalOwned)return setAnalyticsMessage("Confirm that the historical post is yours before importing it.");
    const response=await fetch(`${API}/v1/historical-posts`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...historical,pillar:historical.pillar||voiceProfile?.content_pillars[0],published_at:new Date(historical.published_at).toISOString(),content_is_user_owned:true})});
    const data=await response.json();if(!response.ok)return setAnalyticsMessage(data.detail??"Historical post could not be imported.");
    setAnalyticsRevisionId(data.revision_id);setPredictionRevisionId(data.revision_id);await refreshMemory();setAnalyticsMessage("Owned historical post added to your private baseline library.");
  }

  async function createExperiment(event:FormEvent) {
    event.preventDefault();
    const response=await fetch(`${API}/v1/experiments`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(experimentDraft)});
    const data=await response.json();if(!response.ok)return setAnalyticsMessage(data.detail??"Experiment could not be created.");
    setExperiments(current=>[data,...current]);setExperimentId(data.id);setExperimentDraft({name:"",hypothesis:"",variable:""});setAnalyticsMessage("Experiment tag created. Change one variable when possible.");
  }

  async function saveMetrics(event:FormEvent) {
    event.preventDefault();
    if(!analyticsRevisionId)return setAnalyticsMessage("Select a published revision first.");
    const numeric=Object.fromEntries(Object.entries(metrics).map(([key,value])=>[key,value===""?null:Number(value)]));
    const response=await fetch(`${API}/v1/metric-snapshots`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({post_revision_id:analyticsRevisionId,observed_at:new Date(metricObserved).toISOString(),window_hours:analyticsWindow,...numeric,baseline:metricBaseline,experiment_id:experimentId||null})});
    const data=await response.json();if(!response.ok)return setAnalyticsMessage(data.detail??"Metrics could not be saved.");
    await refreshAnalytics();setAnalyticsMessage(`Saved ${analyticsWindow}-hour snapshot with ${data.engagement_rate??"no"}% measurable engagement.`);
  }

  async function uploadMetricsCsv(file?:File) {
    if(!file)return;
    const form=new FormData();form.append("file",file);
    const response=await fetch(`${API}/v1/metric-snapshots/import-csv`,{method:"POST",body:form});
    const data=await response.json();if(!response.ok)return setAnalyticsMessage(data.detail??"CSV import failed.");
    await refreshAnalytics();setAnalyticsMessage(`${data.created} snapshots imported, ${data.duplicates} duplicates skipped, ${data.errors.length} row errors.`);
  }

  async function predictPerformance() {
    if(!predictionRevisionId)return setAnalyticsMessage("Select an approved or published revision before predicting performance.");
    const response=await fetch(`${API}/v1/predictions`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({post_revision_id:predictionRevisionId,target_window_hours:analyticsWindow})});
    const data=await response.json();if(!response.ok)return setAnalyticsMessage(data.detail??"Prediction could not be created.");
    setPrediction(data);setAnalyticsMessage(`${data.basis.replaceAll("_"," ")} estimate created. Treat it as guidance, never a guarantee.`);
  }

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
    adoptDraft(data);
    setContentMessage("Primary draft ready. Submit the exact revision when you are ready to review it.");
  }

  function adoptDraft(data: PrimaryDraft) {
    setPrimaryDraft(data);
    setEditedDraft({hook:data.hook,body:data.body,cta:data.cta});
    setShowDraftEditor(false);
    setEditClaimsConfirmed(false);
    setApprovalConfirmed(false);
  }

  async function submitDraftReview() {
    if (!primaryDraft) return;
    const response = await fetch(`${API}/v1/posts/${primaryDraft.post_id}/submit-review`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision_id:primaryDraft.revision_id})});
    const data = await response.json();
    if (!response.ok) return setContentMessage(data.detail ?? "The revision could not enter review.");
    adoptDraft(data);
    setContentMessage(`Revision ${data.revision_number} is in review. Approve, request regeneration, edit, or reject it.`);
  }

  async function saveDraftEdit() {
    if (!primaryDraft) return;
    if (!editClaimsConfirmed) return setContentMessage("Confirm that the edited text contains only claims you can support.");
    const response = await fetch(`${API}/v1/posts/${primaryDraft.post_id}/edits`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision_id:primaryDraft.revision_id,...editedDraft,claims_confirmed:true})});
    const data = await response.json();
    if (!response.ok) return setContentMessage(data.detail ?? "The edited revision could not be saved.");
    adoptDraft(data);
    await refreshMemory();
    setContentMessage(`Revision ${data.revision_number} saved as a new draft. Earlier revisions remain unchanged.`);
  }

  function toggleReviewCategory(category: ReviewCategory) {
    setReviewCategories(current=>current.includes(category)?current.filter(item=>item!==category):[...current,category]);
  }

  async function requestRegeneration() {
    if (!primaryDraft) return;
    if (!reviewFeedback.trim() || !reviewCategories.length) return setContentMessage("Choose a feedback category and explain the requested change.");
    const requested = await fetch(`${API}/v1/posts/${primaryDraft.post_id}/reviews`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision_id:primaryDraft.revision_id,action:"REQUEST_CHANGES",reason:reviewFeedback,categories:reviewCategories})});
    const requestData = await requested.json();
    if (!requested.ok) return setContentMessage(requestData.detail ?? "The regeneration feedback could not be recorded.");
    setContentMessage("Feedback recorded. Generating a new draft revision…");
    const response = await fetch(`${API}/v1/posts/${primaryDraft.post_id}/regenerations`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision_id:primaryDraft.revision_id})});
    const data = await response.json();
    if (!response.ok) { adoptDraft(requestData); return setContentMessage(data.detail ?? "Feedback was saved, but regeneration did not complete."); }
    adoptDraft(data);
    setReviewFeedback("");
    setReviewCategories([]);
    setContentMessage(`Revision ${data.revision_number} generated from your structured feedback. It still requires review.`);
  }

  async function rejectDraft() {
    if (!primaryDraft) return;
    if (!rejectionReason.trim()) return setContentMessage("Add a rejection reason first.");
    const response = await fetch(`${API}/v1/posts/${primaryDraft.post_id}/reviews`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision_id:primaryDraft.revision_id,action:"REJECT",reason:rejectionReason})});
    const data = await response.json();
    if (!response.ok) return setContentMessage(data.detail ?? "The rejection could not be recorded.");
    adoptDraft(data);
    setContentMessage("The post was rejected with its reason preserved. This post is now terminal.");
  }

  async function approveDraft() {
    if (!primaryDraft) return;
    if (!approvalConfirmed) return setContentMessage("Confirm the exact revision and its claims before approval.");
    const response = await fetch(`${API}/v1/posts/${primaryDraft.post_id}/reviews`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision_id:primaryDraft.revision_id,action:"APPROVE",claims_confirmed:true})});
    const data = await response.json();
    if (!response.ok) return setContentMessage(data.detail ?? "The revision could not be approved.");
    adoptDraft(data);
    await refreshMemory();
    setContentMessage(`Revision ${data.revision_number} approved by you. It can now be scheduled in the calendar.`);
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#top" aria-label="Liproser home"><span>Li</span><strong>Liproser</strong></a>
      <nav aria-label="Primary navigation">
        <a className="nav-item active" href="#profile"><span>01</span>Profile lab</a>
        <a className="nav-item" href="#voice"><span>02</span>Voice setup<small>v0.2</small></a>
        <a className="nav-item" href="#library"><span>03</span>Library<small>v0.2D</small></a>
        <a className="nav-item" href="#calendar"><span>04</span>Calendar<small>v0.3</small></a>
        <a className="nav-item" href="#analytics"><span>05</span>Analytics<small>v0.4</small></a>
      </nav>
      <div className="privacy-card"><span className="privacy-icon">✓</span><strong>Private by design</strong><p>Your profile remains on this machine. Nothing publishes automatically.</p></div>
      <p className="version">Personal edition · v0.4</p>
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
            <div className="draft-meta"><div><span>{primaryDraft.state.replaceAll("_"," ")} · REVISION {primaryDraft.revision_number}</span><strong>{primaryDraft.pillar}</strong></div><div><span>{primaryDraft.generation_mode === "provider" ? `AI · ${primaryDraft.generation_model}` : primaryDraft.generation_mode === "human_edit" ? "Human edit" : "Safe fallback"}</span><strong>{primaryDraft.state === "APPROVED" ? "Human approved" : primaryDraft.state === "REJECTED" ? "Rejected" : "Not approved"}</strong></div></div>
            {primaryDraft.generation_warning && <p className="draft-warning">{primaryDraft.generation_warning}</p>}
            <article className="linkedin-preview" aria-label="LinkedIn-style draft preview"><div className="preview-author"><span>R</span><div><strong>Your name</strong><small>Your headline · now</small></div><b>•••</b></div><p className="preview-content"><strong>{primaryDraft.hook}</strong>{`\n\n${primaryDraft.body}\n\n${primaryDraft.cta}`}</p><div className="preview-reactions"><span>○ ○</span><span>0 comments · 0 reposts</span></div></article>
            <div className="claim-ledger"><div><strong>Claim ledger</strong><span>{primaryDraft.claims.length} classified</span></div>{primaryDraft.claims.map(claim=><p key={claim.id}><span className={claim.kind.toLowerCase()}>{claim.kind}</span>{claim.claim_text}<small>{claim.source_reference_ids.length ? `${claim.source_reference_ids.length} evidence link` : "No factual source claimed"}</small></p>)}</div>
            {primaryDraft.retrievals.length > 0 && <div className="memory-provenance"><div><strong>First-party references</strong><span>Structure only · never copied</span></div>{primaryDraft.retrievals.map(reference=><p key={reference.revision_id}><span>{Math.round(reference.similarity_score*100)}% related</span><strong>{reference.topic}</strong><small>{reference.pillar} · {reference.embedding_version} · {reference.features.hook_style} hook</small></p>)}</div>}
            <div className="revision-checks"><div><strong>Revision checks</strong><span>Claims, voice, originality, and diversity</span></div>{primaryDraft.checks.map(check=><p key={check.id} className={check.passed?"passed":"failed"}><b>{check.passed?"✓":"!"}</b><span><strong>{check.check_type.replaceAll("_"," ")}</strong><small>{check.severity} · {check.message}</small></span></p>)}</div>
            {showDraftEditor && <div className="draft-editor"><strong>Save changes as a new immutable revision</strong><label><span>Hook</span><textarea aria-label="Edit post hook" value={editedDraft.hook} onChange={event=>setEditedDraft({...editedDraft,hook:event.target.value})} rows={2}/></label><label><span>Body</span><textarea aria-label="Edit post body" value={editedDraft.body} onChange={event=>setEditedDraft({...editedDraft,body:event.target.value})} rows={7}/></label><label><span>CTA</span><textarea aria-label="Edit post CTA" value={editedDraft.cta} onChange={event=>setEditedDraft({...editedDraft,cta:event.target.value})} rows={2}/></label><label className="review-confirm"><input type="checkbox" checked={editClaimsConfirmed} onChange={event=>setEditClaimsConfirmed(event.target.checked)}/><span>I confirm every claim and numeric detail in this edited revision.</span></label><div className="review-buttons"><button className="button primary" onClick={saveDraftEdit}>Save new revision</button><button className="button outline" onClick={()=>setShowDraftEditor(false)}>Cancel edit</button></div></div>}
            {!showDraftEditor && primaryDraft.state !== "REJECTED" && <div className="review-buttons"><button className="button outline" onClick={()=>{setEditedDraft({hook:primaryDraft.hook,body:primaryDraft.body,cta:primaryDraft.cta});setShowDraftEditor(true);}}>Edit as new revision</button>{primaryDraft.state === "DRAFT" && <button className="button primary" onClick={submitDraftReview}>Submit revision for review</button>}</div>}
            {primaryDraft.state === "IN_REVIEW" && <div className="review-console">
              <div className="approval-panel"><strong>Approve exact revision {primaryDraft.revision_number}</strong><label className="review-confirm"><input type="checkbox" checked={approvalConfirmed} onChange={event=>setApprovalConfirmed(event.target.checked)}/><span>I reviewed this exact revision and confirm its claims.</span></label><button className="button primary" onClick={approveDraft}>Approve exact revision</button></div>
              <div className="regeneration-panel"><strong>Request regeneration</strong><div className="feedback-categories">{(["HOOK","TONE","CLARITY","CTA","LENGTH","EVIDENCE"] as ReviewCategory[]).map(category=><label key={category}><input type="checkbox" checked={reviewCategories.includes(category)} onChange={()=>toggleReviewCategory(category)}/><span>{category}</span></label>)}</div><textarea aria-label="Regeneration feedback" value={reviewFeedback} onChange={event=>setReviewFeedback(event.target.value)} rows={3} placeholder="Describe the specific change to make"/><button className="button accent" onClick={requestRegeneration}>Request changes & regenerate</button></div>
              <div className="rejection-panel"><strong>Reject post</strong><textarea aria-label="Post rejection reason" value={rejectionReason} onChange={event=>setRejectionReason(event.target.value)} rows={3} placeholder="Why should this post not continue?"/><button className="button danger" onClick={rejectDraft}>Reject with reason</button></div>
            </div>}
            {primaryDraft.state === "APPROVED" && <p className="review-boundary approved-boundary">Approved by the local owner. Only this exact revision is approved; editing creates a new draft.</p>}
            {primaryDraft.state === "REJECTED" && <p className="review-boundary rejected-boundary">Rejected with a recorded reason. This post cannot be edited, approved, scheduled, or published.</p>}
            {primaryDraft.reviews.length > 0 && <div className="review-history"><strong>Review history</strong>{primaryDraft.reviews.map(event=><p key={event.id}><span>{event.action.replaceAll("_"," ")}</span><small>Revision {event.revision_number}{event.reason ? ` · ${event.reason}` : ""}</small></p>)}</div>}
          </div>}
        </>}
      </section>

      <section className="memory-library" id="library">
        <div className="studio-heading"><div><p className="eyebrow">FIRST-PARTY MEMORY · v0.2D</p><h2>Your approved work becomes a private reference.</h2><p>Only the exact approved revision appears here. Editing, rejecting, deleting, or superseding it removes eligibility. Liproser retrieves structural signals—not third-party posts or reusable copy.</p></div><span className="draft-limit">{memoryRevisions.length} eligible</span></div>
        {memoryRevisions.length === 0 ? <div className="studio-locked"><strong>No eligible revisions yet</strong><p>Approve a reviewed draft to add it. Drafts and rejected posts never enter memory.</p></div> : <div className="memory-grid">{memoryRevisions.map(item=><article key={item.revision_id}><div><span>{item.pillar}</span><span>Revision {item.revision_number}</span></div><h3>{item.topic}</h3><p>{item.features.word_count} words · {item.features.paragraph_count} paragraphs · {item.features.hook_style.toLowerCase()} hook · {item.features.cta_style.toLowerCase()} CTA</p><small>{item.embedding_version} · {item.taxonomy_version}</small></article>)}</div>}
      </section>

      <section className="calendar-section" id="calendar">
        <div className="studio-heading"><div><p className="eyebrow">CALENDAR & REMINDERS · v0.3</p><h2>Turn approved ideas into a dependable rhythm.</h2><p>Plan around your timezone and quiet days. A schedule belongs to one exact approved revision; Liproser never publishes for you.</p></div><span className="draft-limit">Human publish only</span></div>
        <form className="calendar-form" onSubmit={planCalendar}>
          <label><span>Start date</span><input aria-label="Calendar start date" type="date" value={calendarStart} onChange={event=>setCalendarStart(event.target.value)} required/></label>
          <label><span>Weeks</span><input aria-label="Calendar weeks" type="number" min="1" max="8" value={calendarWeeks} onChange={event=>setCalendarWeeks(Number(event.target.value))}/></label>
          <label><span>Posts per week</span><input aria-label="Calendar cadence" type="number" min="1" max="5" value={calendarCadence} onChange={event=>setCalendarCadence(Number(event.target.value))}/></label>
          <label><span>IANA timezone</span><input aria-label="Calendar timezone" value={calendarTimezone} onChange={event=>setCalendarTimezone(event.target.value)} required/></label>
          <button className="button primary" type="submit">Plan calendar</button><p role="status">{calendarMessage}</p>
        </form>
        {calendar && <div className="calendar-grid">{calendar.slots.map(slot=><article key={slot.id} className={slot.status.toLowerCase()}><div><span>Slot {slot.position}</span><b>{slot.status}</b></div><strong>{slot.pillar}</strong><time>{new Date(slot.resolved_utc_at).toLocaleString([], {dateStyle:"medium",timeStyle:"short",timeZone:calendar.timezone})}</time>{slot.status==="PLANNED" && primaryDraft?.state==="APPROVED" && <button className="button accent" onClick={()=>scheduleApproved(slot)}>Schedule approved revision</button>}</article>)}</div>}
        {schedules.length>0 && <div className="schedule-list"><strong>Schedules</strong>{schedules.map(item=><article key={item.id}><div><span>{item.status.replaceAll("_"," ")}</span><time>{new Date(item.resolved_utc_at).toLocaleString()}</time></div>{item.status==="ACTIVE"&&<button className="button outline" onClick={()=>preparePublish(item)}>Prepare copy & publish now</button>}</article>)}</div>}
        {publishAction?.state==="ACTION_REQUIRED" && <div className="publish-panel"><div><strong>Ready for your manual publish</strong><span>No automatic LinkedIn action occurs.</span></div><textarea readOnly value={publishAction.formatted_content} rows={8} aria-label="Formatted post to copy"/><button className="button accent" onClick={()=>navigator.clipboard.writeText(publishAction.formatted_content)}>Copy formatted post</button><label><span>Published post URL <small>optional</small></span><input aria-label="Published post URL" value={publishedUrl} onChange={event=>setPublishedUrl(event.target.value)} placeholder="https://www.linkedin.com/feed/update/…"/></label><button className="button primary" onClick={confirmPublished}>I published this exact revision</button></div>}
        {publishAction?.state==="PUBLISHED" && <p className="publication-confirmed">✓ Publication confirmed by you. {publishAction.published_url&&<a href={publishAction.published_url}>Open recorded post</a>}</p>}
        <div className="preference-panel"><div><strong>Learned preferences</strong><span>Created only after two matching feedback signals; every rule is reversible.</span></div>{preferences.length===0?<p>No repeated preference signals yet.</p>:preferences.map(item=><article key={item.id}><div><strong>{item.category.replaceAll("_"," ")}</strong><small>{item.evidence_count} signals · version {item.version}</small><p>{item.instruction}</p></div><button className={`preference-toggle ${item.active?"active":""}`} onClick={()=>togglePreference(item)}>{item.active?"Enabled":"Disabled"}</button></article>)}</div>
      </section>

      <section className="analytics-section" id="analytics">
        <div className="studio-heading"><div><p className="eyebrow">ANALYTICS & PREDICTION · v0.4</p><h2>Learn from comparable outcomes, not vanity totals.</h2><p>Import only your own published posts and compare snapshots with the same observation window. Predictions explain their evidence basis and never promise reach.</p></div><span className="draft-limit">Manual or CSV</span></div>
        <div className="analytics-grid">
          <form className="analytics-panel" onSubmit={importHistoricalPost}>
            <div><strong>Import an owned historical post</strong><span>Build a pre-Liproser baseline without scraping.</span></div>
            <label><span>Controlled pillar</span><select aria-label="Historical post pillar" value={historical.pillar} onChange={event=>setHistorical({...historical,pillar:event.target.value})}>{!voiceProfile&&<option value="">Save a voice profile first</option>}{voiceProfile?.content_pillars.map(pillar=><option key={pillar}>{pillar}</option>)}</select></label>
            <label><span>Topic</span><input aria-label="Historical post topic" value={historical.topic} onChange={event=>setHistorical({...historical,topic:event.target.value})} required/></label>
            <label><span>Hook</span><textarea aria-label="Historical post hook" value={historical.hook} onChange={event=>setHistorical({...historical,hook:event.target.value})} rows={2} required/></label>
            <label><span>Body</span><textarea aria-label="Historical post body" value={historical.body} onChange={event=>setHistorical({...historical,body:event.target.value})} rows={5} required/></label>
            <label><span>CTA <small>optional</small></span><input aria-label="Historical post CTA" value={historical.cta} onChange={event=>setHistorical({...historical,cta:event.target.value})}/></label>
            <label><span>Published at</span><input aria-label="Historical post published at" type="datetime-local" value={historical.published_at} onChange={event=>setHistorical({...historical,published_at:event.target.value})} required/></label>
            <label className="analytics-check"><input type="checkbox" checked={historicalOwned} onChange={event=>setHistoricalOwned(event.target.checked)}/><span>I confirm this post is mine or I am authorized to use it privately.</span></label>
            <button className="button primary" type="submit" disabled={!voiceProfile}>Import owned post</button>
          </form>

          <form className="analytics-panel" onSubmit={createExperiment}>
            <div><strong>Create an experiment tag</strong><span>Change one element so later comparisons stay interpretable.</span></div>
            <label><span>Name</span><input aria-label="Experiment name" value={experimentDraft.name} onChange={event=>setExperimentDraft({...experimentDraft,name:event.target.value})} placeholder="Question CTA" required/></label>
            <label><span>Hypothesis</span><textarea aria-label="Experiment hypothesis" value={experimentDraft.hypothesis} onChange={event=>setExperimentDraft({...experimentDraft,hypothesis:event.target.value})} rows={3} placeholder="A specific closing question increases meaningful replies." required/></label>
            <label><span>One variable</span><input aria-label="Experiment variable" value={experimentDraft.variable} onChange={event=>setExperimentDraft({...experimentDraft,variable:event.target.value})} placeholder="CTA" required/></label>
            <button className="button outline" type="submit">Create experiment tag</button>
          </form>
        </div>

        <form className="metric-form" onSubmit={saveMetrics}>
          <div className="metric-heading"><div><strong>Add a comparable metric snapshot</strong><span>Use the same observation window—such as 24 or 168 hours—across posts.</span></div><label className="csv-button">Import CSV<input type="file" accept=".csv,text/csv" aria-label="Import analytics CSV" onChange={event=>uploadMetricsCsv(event.target.files?.[0])}/></label></div>
          <div className="metric-grid">
            <label className="metric-wide"><span>Published revision for metrics</span><select aria-label="Analytics published revision" value={analyticsRevisionId} onChange={event=>setAnalyticsRevisionId(event.target.value)} required><option value="">Select your published post</option>{memoryRevisions.filter(item=>item.state==="PUBLISHED").map(item=><option key={item.revision_id} value={item.revision_id}>{item.topic} · revision {item.revision_number}</option>)}</select></label>
            <label className="metric-wide"><span>Approved or published revision to predict</span><select aria-label="Prediction revision" value={predictionRevisionId} onChange={event=>setPredictionRevisionId(event.target.value)}><option value="">Select a prediction candidate</option>{memoryRevisions.map(item=><option key={item.revision_id} value={item.revision_id}>{item.topic} · {item.state.replaceAll("_"," ")}</option>)}</select></label>
            <label><span>Observed at</span><input aria-label="Metrics observed at" type="datetime-local" value={metricObserved} onChange={event=>setMetricObserved(event.target.value)} required/></label>
            <label><span>Window hours</span><input aria-label="Metrics observation window" type="number" min="1" max="8760" value={analyticsWindow} onChange={event=>{const value=Number(event.target.value);setAnalyticsWindow(value);refreshAnalytics(value);}} required/></label>
            {(Object.keys(metrics) as (keyof typeof metrics)[]).map(key=><label key={key}><span>{key.replaceAll("_"," ")}</span><input aria-label={`Metric ${key.replaceAll("_"," ")}`} type="number" min={key==="follower_delta"?undefined:0} value={metrics[key]} onChange={event=>setMetrics({...metrics,[key]:event.target.value})}/></label>)}
            <label className="metric-wide"><span>Experiment <small>optional</small></span><select aria-label="Metric experiment" value={experimentId} onChange={event=>setExperimentId(event.target.value)}><option value="">No experiment</option>{experiments.map(item=><option key={item.id} value={item.id}>{item.name} · {item.variable}</option>)}</select></label>
            <label className="analytics-check metric-wide"><input type="checkbox" checked={metricBaseline} onChange={event=>setMetricBaseline(event.target.checked)}/><span>Mark this as a pre-Liproser baseline snapshot.</span></label>
          </div>
          <div className="metric-actions"><button className="button primary" type="submit">Save metric snapshot</button><button className="button accent" type="button" onClick={predictPerformance}>Predict selected revision</button><p role="status">{analyticsMessage}</p></div>
        </form>

        <div className="analytics-results">
          <article><span>Comparable posts</span><strong>{analyticsSummary?.comparable_post_count??0}</strong><small>{analyticsWindow}-hour window</small></article>
          <article><span>Baseline engagement</span><strong>{analyticsSummary?.baseline_engagement_rate!=null?`${analyticsSummary.baseline_engagement_rate}%`:"—"}</strong><small>Pre-Liproser only</small></article>
          <article><span>Current engagement</span><strong>{analyticsSummary?.current_engagement_rate!=null?`${analyticsSummary.current_engagement_rate}%`:"—"}</strong><small>{analyticsSummary?.lift_percent!=null?`${analyticsSummary.lift_percent}% vs baseline`:"Needs a matching baseline"}</small></article>
          <article><span>Prediction error</span><strong>{analyticsSummary?.mean_absolute_error!=null?`${analyticsSummary.mean_absolute_error}pp`:"—"}</strong><small>{analyticsSummary?.calibration_count??0} evaluated predictions</small></article>
        </div>
        {prediction&&<div className="prediction-panel"><div><span className={`prediction-bucket ${prediction.bucket.toLowerCase()}`}>{prediction.bucket}</span><div><strong>{prediction.expected_engagement_rate}% expected engagement</strong><small>{prediction.interval[0]}–{prediction.interval[1]}% interval · {prediction.basis.replaceAll("_"," ")}</small></div></div><div className="prediction-factors">{prediction.factors.map(factor=><article key={factor.feature}><span className={factor.impact.toLowerCase()}>{factor.impact}</span><strong>{factor.feature}</strong><p>{factor.explanation}</p></article>)}</div>{prediction.recommended_change&&<p className="recommended-change"><strong>One change most likely to help</strong>{prediction.recommended_change}</p>}<ul>{prediction.limitations.map(item=><li key={item}>{item}</li>)}</ul></div>}
        {analyticsSummary?.best_pillars.length?<div className="pillar-performance"><strong>Best comparable pillars</strong>{analyticsSummary.best_pillars.map(item=><span key={item.pillar}>{item.pillar}<b>{item.engagement_rate}% · {item.post_count} post{item.post_count===1?"":"s"}</b></span>)}</div>:null}
      </section>

      <footer><strong>Liproser</strong><span>Evidence over exaggeration.</span><small>Personal edition · v0.4 · Data stays local</small></footer>
    </main>
  </div>;
}
