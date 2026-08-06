import { useEffect, useMemo, useState } from "react";

import {
  createObservationPeriod,
  createSavedOption,
  deleteObservationPeriod,
  endObservationPeriod,
  getObservationPeriods,
  updateObservationPeriod,
} from "../services/api";
import type { ObservationPeriod } from "../types/observation";
import type { SavedOption } from "../types/event";
import { getLocalDayRange } from "../utils/date";

interface Props {
  dogId: string;
  options: SavedOption[];
  refreshKey: number;
  onOptionCreated: (option: SavedOption) => void;
  onChanged: () => void;
}

function localDateTime(date = new Date()): string {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}

export function ObservationPeriods({
  dogId,
  options,
  refreshKey,
  onOptionCreated,
  onChanged,
}: Props) {
  const reasons = useMemo(
    () => options.filter((option) => option.category === "OBSERVATION_REASON" && option.is_active),
    [options],
  );
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
  const [editStart, setEditStart] = useState("");
  const [editEnd, setEditEnd] = useState("");
  const [editReasonId, setEditReasonId] = useState("");
  const [editNotes, setEditNotes] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const { start, end } = getLocalDayRange();
        setPeriods(await getObservationPeriods(dogId, start, end, false, controller.signal));
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") setError(err.message);
      }
    }
    void load();
    return () => controller.abort();
  }, [dogId, refreshKey]);

  const active = periods.find((period) => period.end_time === null) ?? null;

  async function addReason() {
    const name = customReason.trim();
    if (!name) return;
    setSaving(true); setError(null);
    try {
      const option = await createSavedOption(dogId, "OBSERVATION_REASON", name);
      onOptionCreated(option); setReasonId(option.id); setCustomReason("");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save reason."); }
    finally { setSaving(false); }
  }

  async function startNow() {
    if (!reasonId) return;
    setSaving(true); setError(null);
    try {
      await createObservationPeriod({ dog_id: dogId, reason_option_id: reasonId, notes: notes.trim() || null });
      setNotes(""); onChanged();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not start period."); }
    finally { setSaving(false); }
  }

  async function endNow() {
    if (!active) return;
    setSaving(true); setError(null);
    try { await endObservationPeriod(active.id); onChanged(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not end period."); }
    finally { setSaving(false); }
  }

  async function addManual() {
    if (!reasonId || !manualStart || !manualEnd) return;
    setSaving(true); setError(null);
    try {
      await createObservationPeriod({
        dog_id: dogId,
        start_time: new Date(manualStart).toISOString(),
        end_time: new Date(manualEnd).toISOString(),
        reason_option_id: reasonId,
        notes: notes.trim() || null,
      });
      setNotes(""); setManualStart(localDateTime()); setManualEnd(localDateTime()); onChanged();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not add period."); }
    finally { setSaving(false); }
  }

  function beginEdit(period: ObservationPeriod) {
    setEditing(period);
    setEditStart(localDateTime(new Date(period.start_time)));
    setEditEnd(period.end_time ? localDateTime(new Date(period.end_time)) : "");
    setEditReasonId(period.reason_option_id ?? "");
    setEditNotes(period.notes ?? "");
    setError(null);
  }

  async function saveEdit() {
    if (!editing || !editStart || !editReasonId) return;
    setSaving(true); setError(null);
    try {
      await updateObservationPeriod(editing.id, {
        start_time: new Date(editStart).toISOString(),
        end_time: editEnd ? new Date(editEnd).toISOString() : null,
        reason_option_id: editReasonId,
        notes: editNotes.trim() || null,
      });
      setEditing(null); onChanged();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not update period."); }
    finally { setSaving(false); }
  }

  async function remove(period: ObservationPeriod) {
    if (!window.confirm(`Delete the ${period.reason_name ?? "unobserved"} period?`)) return;
    try { await deleteObservationPeriod(period.id); if (editing?.id === period.id) setEditing(null); onChanged(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not delete period."); }
  }

  return (
    <section className="observation-card">
      <div className="section-heading">
        <div><p className="eyebrow">Observation coverage</p><h2>Unobserved time</h2></div>
        {active && <span className="active-period-badge">Active</span>}
      </div>

      {error && <p className="event-error" role="alert">{error}</p>}

      {active ? (
        <div className="active-observation">
          <div><strong>{active.reason_name ?? "Unobserved"}</strong><p>Started {new Date(active.start_time).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}</p></div>
          <button className="save-button" type="button" disabled={saving} onClick={() => void endNow()}>{saving ? "Ending…" : "I’m observing again"}</button>
        </div>
      ) : (
        <div className="observation-start-row">
          <label className="field-label">Reason<select value={reasonId} onChange={(event) => setReasonId(event.target.value)}><option value="">Choose a reason</option>{reasons.map((reason) => <option key={reason.id} value={reason.id}>{reason.name}</option>)}</select></label>
          <label className="field-label">Notes <span>Optional</span><input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Where Maverick is or who is watching" /></label>
          <button className="save-button full-width" type="button" disabled={!reasonId || saving} onClick={() => void startNow()}>{saving ? "Starting…" : "Start unobserved period"}</button>
        </div>
      )}

      <div className="inline-create"><input value={customReason} onChange={(event) => setCustomReason(event.target.value)} placeholder="Add another reusable reason" /><button type="button" disabled={saving || !customReason.trim()} onClick={() => void addReason()}>Add</button></div>

      <button className="secondary-button full-width observation-manual-toggle" type="button" onClick={() => setExpanded((current) => !current)}>{expanded ? "Hide manual entry" : "Add a completed period"}</button>

      {expanded && (
        <div className="observation-manual-form">
          <div className="observation-time-grid">
            <label className="field-label">Start<input type="datetime-local" value={manualStart} onChange={(event) => setManualStart(event.target.value)} /></label>
            <label className="field-label">End<input type="datetime-local" value={manualEnd} onChange={(event) => setManualEnd(event.target.value)} /></label>
          </div>
          <button className="save-button full-width" type="button" disabled={!reasonId || !manualStart || !manualEnd || saving} onClick={() => void addManual()}>Add completed period</button>
        </div>
      )}

      {periods.length > 0 && <div className="observation-list"><h3>Today’s periods</h3>{periods.map((period) => <div className="observation-list-item" key={period.id}><div><strong>{period.reason_name ?? "Unobserved"}</strong><p>{new Date(period.start_time).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}–{period.end_time ? new Date(period.end_time).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }) : "Now"}</p></div><div className="timeline-actions"><button type="button" onClick={() => beginEdit(period)}>Edit</button><button className="delete-action" type="button" onClick={() => void remove(period)}>Delete</button></div></div>)}</div>}

      {editing && (
        <div className="edit-event-panel">
          <p className="eyebrow">Edit period</p><h3>{editing.reason_name ?? "Unobserved"}</h3>
          <div className="observation-time-grid"><label className="field-label">Start<input type="datetime-local" value={editStart} onChange={(event) => setEditStart(event.target.value)} /></label><label className="field-label">End <span>Blank means active</span><input type="datetime-local" value={editEnd} onChange={(event) => setEditEnd(event.target.value)} /></label></div>
          <label className="field-label">Reason<select value={editReasonId} onChange={(event) => setEditReasonId(event.target.value)}>{reasons.map((reason) => <option key={reason.id} value={reason.id}>{reason.name}</option>)}</select></label>
          <label className="field-label">Notes<textarea rows={3} maxLength={500} value={editNotes} onChange={(event) => setEditNotes(event.target.value)} /></label>
          <div className="form-actions"><button className="cancel-button" type="button" onClick={() => setEditing(null)}>Cancel</button><button className="save-button" type="button" disabled={saving || !editStart || !editReasonId} onClick={() => void saveEdit()}>{saving ? "Saving…" : "Save changes"}</button></div>
        </div>
      )}
    </section>
  );
}
