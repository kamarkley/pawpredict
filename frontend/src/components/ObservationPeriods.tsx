import { useEffect, useMemo, useState } from "react";

import {
  createObservationPeriod,
  createSavedOption,
  deleteObservationPeriod,
  endObservationPeriod,
  getObservationPeriods,
  updateObservationPeriod,
} from "../services/api";
import type { SavedOption } from "../types/event";
import type { ObservationPeriod, ObservationPeriodUpdate } from "../types/observation";
import { getLocalDayRange } from "../utils/date";

interface Props { dogId: string; options: SavedOption[]; refreshKey: number; onOptionCreated: (option: SavedOption) => void; onChanged: () => void; }

type LikelyState = "SLEEPING" | "AWAKE" | "MIXED" | "UNKNOWN";

function localDateTime(date = new Date()): string {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function OutcomeFields({ peed, pooped, location, likelyState, cameraChecked, onChange }: {
  peed: boolean; pooped: boolean; location: string; likelyState: LikelyState; cameraChecked: boolean;
  onChange: (values: { peed?: boolean; pooped?: boolean; location?: string; likelyState?: LikelyState; cameraChecked?: boolean }) => void;
}) {
  return (
    <div className="observation-outcomes">
      <div><p className="field-group-label">What happened while unobserved?</p><div className="outcome-toggle-row"><label><input type="checkbox" checked={peed} onChange={(e) => onChange({ peed: e.target.checked })} /> Pee</label><label><input type="checkbox" checked={pooped} onChange={(e) => onChange({ pooped: e.target.checked })} /> Poop</label></div></div>
      {(peed || pooped) && <label className="field-label">Known potty location <span>Optional</span><select value={location} onChange={(e) => onChange({ location: e.target.value })}><option value="">Unknown</option><option>Litter Box</option><option>Outside</option><option>Pee Pad</option><option>Accident</option><option>Other</option></select></label>}
      <label className="field-label">Likely state<select value={likelyState} onChange={(e) => onChange({ likelyState: e.target.value as LikelyState })}><option value="SLEEPING">Mostly sleeping</option><option value="AWAKE">Mostly awake</option><option value="MIXED">Mixed</option><option value="UNKNOWN">Unknown</option></select></label>
      <label className="camera-check"><input type="checkbox" checked={cameraChecked} onChange={(e) => onChange({ cameraChecked: e.target.checked })} /> I checked in by camera</label>
      <p className="helper-copy">These are stored as interval-level evidence, not fake exact-time potty events, so later predictions can use them safely.</p>
    </div>
  );
}

export function ObservationPeriods({ dogId, options, refreshKey, onOptionCreated, onChanged }: Props) {
  const reasons = useMemo(() => options.filter((option) => option.category === "OBSERVATION_REASON" && option.is_active), [options]);
  const [periods, setPeriods] = useState<ObservationPeriod[]>([]);
  const [reasonId, setReasonId] = useState("");
  const [notes, setNotes] = useState("");
  const [manualStart, setManualStart] = useState(localDateTime());
  const [manualEnd, setManualEnd] = useState(localDateTime());
  const [customReason, setCustomReason] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<ObservationPeriod | null>(null);
  const [editStart, setEditStart] = useState(""); const [editEnd, setEditEnd] = useState(""); const [editReasonId, setEditReasonId] = useState(""); const [editNotes, setEditNotes] = useState("");
  const [peed, setPeed] = useState(false); const [pooped, setPooped] = useState(false); const [pottyLocation, setPottyLocation] = useState(""); const [likelyState, setLikelyState] = useState<LikelyState>("SLEEPING"); const [cameraChecked, setCameraChecked] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const { start, end } = getLocalDayRange();
    getObservationPeriods(dogId, start, end, false, controller.signal).then(setPeriods).catch((err: unknown) => { if (err instanceof Error && err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, [dogId, refreshKey]);

  const active = periods.find((period) => period.end_time === null) ?? null;
  const outcomePayload = (): ObservationPeriodUpdate => ({ peed_during: peed || null, pooped_during: pooped || null, potty_location: pottyLocation || null, likely_state: likelyState, camera_checked: cameraChecked });
  const resetOutcomes = () => { setPeed(false); setPooped(false); setPottyLocation(""); setLikelyState("SLEEPING"); setCameraChecked(false); };

  async function addReason() { const name = customReason.trim(); if (!name) return; setSaving(true); try { const option = await createSavedOption(dogId, "OBSERVATION_REASON", name); onOptionCreated(option); setReasonId(option.id); setCustomReason(""); } catch (err) { setError(err instanceof Error ? err.message : "Could not save reason."); } finally { setSaving(false); } }
  async function startNow() { if (!reasonId) return; setSaving(true); try { await createObservationPeriod({ dog_id: dogId, reason_option_id: reasonId, notes: notes.trim() || null, likely_state: "SLEEPING", camera_checked: false }); setNotes(""); resetOutcomes(); onChanged(); } catch (err) { setError(err instanceof Error ? err.message : "Could not start period."); } finally { setSaving(false); } }
  async function endNow() { if (!active) return; setSaving(true); try { await updateObservationPeriod(active.id, outcomePayload()); await endObservationPeriod(active.id); resetOutcomes(); onChanged(); } catch (err) { setError(err instanceof Error ? err.message : "Could not end period."); } finally { setSaving(false); } }
  async function addManual() { if (!reasonId || !manualStart || !manualEnd) return; setSaving(true); try { await createObservationPeriod({ dog_id: dogId, start_time: new Date(manualStart).toISOString(), end_time: new Date(manualEnd).toISOString(), reason_option_id: reasonId, notes: notes.trim() || null, ...outcomePayload() }); setNotes(""); resetOutcomes(); onChanged(); } catch (err) { setError(err instanceof Error ? err.message : "Could not add period."); } finally { setSaving(false); } }

  function beginEdit(period: ObservationPeriod) { setEditing(period); setEditStart(localDateTime(new Date(period.start_time))); setEditEnd(period.end_time ? localDateTime(new Date(period.end_time)) : ""); setEditReasonId(period.reason_option_id ?? ""); setEditNotes(period.notes ?? ""); setPeed(Boolean(period.peed_during)); setPooped(Boolean(period.pooped_during)); setPottyLocation(period.potty_location ?? ""); setLikelyState(period.likely_state ?? "UNKNOWN"); setCameraChecked(period.camera_checked); }
  async function saveEdit() { if (!editing || !editStart || !editReasonId) return; setSaving(true); try { await updateObservationPeriod(editing.id, { start_time: new Date(editStart).toISOString(), end_time: editEnd ? new Date(editEnd).toISOString() : null, reason_option_id: editReasonId, notes: editNotes.trim() || null, ...outcomePayload() }); setEditing(null); resetOutcomes(); onChanged(); } catch (err) { setError(err instanceof Error ? err.message : "Could not update period."); } finally { setSaving(false); } }
  async function remove(period: ObservationPeriod) { if (!window.confirm(`Delete the ${period.reason_name ?? "unobserved"} period?`)) return; await deleteObservationPeriod(period.id); if (editing?.id === period.id) setEditing(null); onChanged(); }

  return (
    <section className="observation-card">
      <div className="section-heading"><div><p className="eyebrow">Observation coverage</p><h2>Unobserved time</h2><p className="section-subcopy">Tell PawPredict what you know without pretending you know the exact minute.</p></div>{active && <span className="active-period-badge">Active</span>}</div>
      {error && <p className="event-error">{error}</p>}
      {active ? (
        <div className="active-observation-panel"><div className="active-observation"><div><strong>{active.reason_name ?? "Unobserved"}</strong><p>Started {new Date(active.start_time).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}</p></div></div><OutcomeFields peed={peed} pooped={pooped} location={pottyLocation} likelyState={likelyState} cameraChecked={cameraChecked} onChange={(v) => { if (v.peed !== undefined) setPeed(v.peed); if (v.pooped !== undefined) setPooped(v.pooped); if (v.location !== undefined) setPottyLocation(v.location); if (v.likelyState) setLikelyState(v.likelyState); if (v.cameraChecked !== undefined) setCameraChecked(v.cameraChecked); }} /><button className="save-button full-width" type="button" disabled={saving} onClick={() => void endNow()}>{saving ? "Ending…" : "I’m observing again"}</button></div>
      ) : (
        <div className="observation-start-row"><label className="field-label">Reason<select value={reasonId} onChange={(e) => setReasonId(e.target.value)}><option value="">Choose a reason</option>{reasons.map((reason) => <option key={reason.id} value={reason.id}>{reason.name}</option>)}</select></label><label className="field-label">Notes <span>Optional</span><input value={notes} onChange={(e) => setNotes(e.target.value)} /></label><button className="save-button" disabled={!reasonId || saving} type="button" onClick={() => void startNow()}>Start unobserved time</button></div>
      )}

      {!active && <><button className="secondary-button observation-manual-toggle" type="button" onClick={() => setExpanded((v) => !v)}>{expanded ? "Hide backfill" : "Add past unobserved period"}</button>{expanded && <div className="observation-manual-form"><div className="observation-time-grid"><label className="field-label">Start<input type="datetime-local" value={manualStart} onChange={(e) => setManualStart(e.target.value)} /></label><label className="field-label">End<input type="datetime-local" value={manualEnd} onChange={(e) => setManualEnd(e.target.value)} /></label></div><OutcomeFields peed={peed} pooped={pooped} location={pottyLocation} likelyState={likelyState} cameraChecked={cameraChecked} onChange={(v) => { if (v.peed !== undefined) setPeed(v.peed); if (v.pooped !== undefined) setPooped(v.pooped); if (v.location !== undefined) setPottyLocation(v.location); if (v.likelyState) setLikelyState(v.likelyState); if (v.cameraChecked !== undefined) setCameraChecked(v.cameraChecked); }} /><button className="save-button full-width" type="button" disabled={!reasonId || saving} onClick={() => void addManual()}>Add period</button></div>}</>}

      <div className="inline-create"><input placeholder="Add another reason" value={customReason} onChange={(e) => setCustomReason(e.target.value)} /><button type="button" onClick={() => void addReason()}>Add</button></div>

      {periods.filter((p) => p.end_time).length > 0 && <div className="observation-list"><h3>Today’s gaps</h3>{periods.filter((p) => p.end_time).map((period) => <div className="observation-list-item" key={period.id}><div><strong>{period.reason_name}</strong><p>{new Date(period.start_time).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}–{period.end_time && new Date(period.end_time).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}</p><small>{[period.peed_during && "pee", period.pooped_during && "poop", period.potty_location, period.likely_state === "SLEEPING" && "mostly sleeping", period.camera_checked && "camera checked"].filter(Boolean).join(" · ")}</small></div><div className="timeline-actions"><button type="button" onClick={() => beginEdit(period)}>Edit</button><button type="button" className="delete-action" onClick={() => void remove(period)}>Delete</button></div></div>)}</div>}

      {editing && <div className="edit-event-panel"><h3>Edit unobserved period</h3><div className="observation-time-grid"><label className="field-label">Start<input type="datetime-local" value={editStart} onChange={(e) => setEditStart(e.target.value)} /></label><label className="field-label">End<input type="datetime-local" value={editEnd} onChange={(e) => setEditEnd(e.target.value)} /></label></div><label className="field-label">Reason<select value={editReasonId} onChange={(e) => setEditReasonId(e.target.value)}>{reasons.map((reason) => <option key={reason.id} value={reason.id}>{reason.name}</option>)}</select></label><OutcomeFields peed={peed} pooped={pooped} location={pottyLocation} likelyState={likelyState} cameraChecked={cameraChecked} onChange={(v) => { if (v.peed !== undefined) setPeed(v.peed); if (v.pooped !== undefined) setPooped(v.pooped); if (v.location !== undefined) setPottyLocation(v.location); if (v.likelyState) setLikelyState(v.likelyState); if (v.cameraChecked !== undefined) setCameraChecked(v.cameraChecked); }} /><label className="field-label">Notes<textarea value={editNotes} onChange={(e) => setEditNotes(e.target.value)} /></label><div className="form-actions"><button className="cancel-button" type="button" onClick={() => { setEditing(null); resetOutcomes(); }}>Cancel</button><button className="save-button" type="button" onClick={() => void saveEdit()}>Save changes</button></div></div>}
    </section>
  );
}
