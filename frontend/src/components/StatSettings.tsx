import { useEffect, useState } from "react";

import { getStatPreferences, updateStatPreferences } from "../services/api";
import type { StatPreference } from "../types/stats";

interface Props {
  dogId: string;
  refreshKey: number;
  onChanged: () => void;
}

export function StatSettings({ dogId, refreshKey, onChanged }: Props) {
  const [preferences, setPreferences] = useState<StatPreference[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getStatPreferences(dogId, controller.signal)
      .then(setPreferences)
      .catch((err: unknown) => {
        if (err instanceof Error && err.name !== "AbortError") setError(err.message);
      });
    return () => controller.abort();
  }, [dogId, refreshKey]);

  function toggle(code: string) {
    setPreferences((current) => current.map((item) => (
      item.code === code ? { ...item, is_enabled: !item.is_enabled } : item
    )));
  }

  function move(code: string, direction: -1 | 1) {
    setPreferences((current) => {
      const ordered = [...current].sort((a, b) => a.display_order - b.display_order);
      const index = ordered.findIndex((item) => item.code === code);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= ordered.length) return current;
      [ordered[index], ordered[target]] = [ordered[target], ordered[index]];
      return ordered.map((item, position) => ({ ...item, display_order: position + 1 }));
    });
  }

  async function save() {
    const enabledCodes = [...preferences]
      .sort((a, b) => a.display_order - b.display_order)
      .filter((item) => item.is_enabled)
      .map((item) => item.code);

    setSaving(true);
    setError(null);
    try {
      setPreferences(await updateStatPreferences(dogId, enabledCodes));
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save dashboard preferences.");
    } finally {
      setSaving(false);
    }
  }

  const ordered = [...preferences].sort((a, b) => a.display_order - b.display_order);

  return (
    <section className="settings-card settings-section">
      <div className="settings-section-heading">
        <div>
          <p className="eyebrow">Dashboard</p>
          <h2>Choose daily stats</h2>
          <p>Select the cards shown on Insights and arrange their order.</p>
        </div>
      </div>
      {error && <p className="event-error">{error}</p>}
      <div className="stat-preference-list">
        {ordered.map((item, index) => (
          <div className="stat-preference-row" key={item.code}>
            <label>
              <input type="checkbox" checked={item.is_enabled} onChange={() => toggle(item.code)} />
              <span><strong>{item.display_name}</strong><small>{item.description}</small></span>
            </label>
            <div className="reorder-actions">
              <button type="button" disabled={index === 0} onClick={() => move(item.code, -1)} aria-label={`Move ${item.display_name} up`}>↑</button>
              <button type="button" disabled={index === ordered.length - 1} onClick={() => move(item.code, 1)} aria-label={`Move ${item.display_name} down`}>↓</button>
            </div>
          </div>
        ))}
      </div>
      <button className="save-button full-width" disabled={saving} type="button" onClick={() => void save()}>
        {saving ? "Saving…" : "Save dashboard choices"}
      </button>
    </section>
  );
}
