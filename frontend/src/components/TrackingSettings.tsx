import { useEffect, useState } from "react";

import { getEventPreferences, updateEventPreferences } from "../services/api";
import type { EventPreference } from "../types/event";

interface Props { dogId: string; refreshKey: number; onChanged: () => void; }

export function TrackingSettings({ dogId, refreshKey, onChanged }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [preferences, setPreferences] = useState<EventPreference[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getEventPreferences(dogId, controller.signal).then(setPreferences).catch((err: unknown) => {
      if (err instanceof Error && err.name !== "AbortError") setError(err.message);
    });
    return () => controller.abort();
  }, [dogId, refreshKey]);

  function toggle(id: number) {
    setPreferences((current) => current.map((item) => item.event_type.id === id ? { ...item, is_enabled: !item.is_enabled } : item));
  }

  async function save() {
    const enabled = preferences.filter((item) => item.is_enabled).map((item) => item.event_type.id);
    setSaving(true); setError(null);
    try { setPreferences(await updateEventPreferences(dogId, enabled)); onChanged(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not save preferences."); }
    finally { setSaving(false); }
  }

  return (
    <section className="settings-card">
      <button className="manual-log-toggle" type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}><span><span className="eyebrow">Personalize</span><strong>Choose what to track</strong></span><span>{expanded ? "−" : "+"}</span></button>
      {expanded && <div className="settings-body">{error && <p className="event-error">{error}</p>}<div className="tracking-grid">{preferences.map((item) => <label className="tracking-toggle" key={item.event_type.id}><input type="checkbox" checked={item.is_enabled} onChange={() => toggle(item.event_type.id)} /><span>{item.event_type.display_name}</span></label>)}</div><button className="save-button full-width" disabled={saving} type="button" onClick={() => void save()}>{saving ? "Saving…" : "Save tracking choices"}</button></div>}
    </section>
  );
}
