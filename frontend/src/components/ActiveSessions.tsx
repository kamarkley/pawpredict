import { useCallback, useEffect, useMemo, useState } from "react";

import { createEvent, getEvents } from "../services/api";
import type { EventType, LoggedEvent } from "../types/event";

const SESSION_CODES = new Set(["SLEEP", "SLEEP_NIGHT", "WALK"]);
const SESSION_ICONS: Record<string, string> = { SLEEP: "😴", SLEEP_NIGHT: "🌙", WALK: "🦮" };

interface Props {
  dogId: string;
  eventTypes: EventType[];
  allEventTypes: EventType[];
  refreshKey: number;
  onEventSaved: () => void;
}

function durationLabel(startIso: string, nowMs: number): string {
  const minutes = Math.max(0, Math.floor((nowMs - new Date(startIso).getTime()) / 60000));
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  if (!hours) return `${minutes}m`;
  return remainder ? `${hours}h ${remainder}m` : `${hours}h`;
}

export function ActiveSessions({ dogId, eventTypes, allEventTypes, refreshKey, onEventSaved }: Props) {
  const sessionTypes = useMemo(
    () => eventTypes.filter((type) => SESSION_CODES.has(type.code)),
    [eventTypes],
  );
  const sessionCatalog = useMemo(
    () => allEventTypes.filter((type) => SESSION_CODES.has(type.code)),
    [allEventTypes],
  );
  const [events, setEvents] = useState<LoggedEvent[]>([]);
  const [busyCode, setBusyCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const fetchSessionEvents = useCallback(async (signal?: AbortSignal) => {
    if (!sessionCatalog.length) return [] as LoggedEvent[];
    const end = new Date(Date.now() + 60_000);
    const start = new Date();
    start.setDate(start.getDate() - 30);
    return getEvents(dogId, start.toISOString(), end.toISOString(), signal);
  }, [dogId, sessionCatalog.length]);

  useEffect(() => {
    const controller = new AbortController();
    void fetchSessionEvents(controller.signal)
      .then((rows) => {
        if (!controller.signal.aborted) setEvents(rows);
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name !== "AbortError") setError(err.message);
      });
    return () => controller.abort();
  }, [fetchSessionEvents, refreshKey]);

  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  const activeByCode = useMemo(() => {
    const result = new Map<string, LoggedEvent>();
    for (const type of sessionCatalog) {
      const latest = events.find((event) => event.event_type_code === type.code && event.state);
      if (latest?.state === "START") result.set(type.code, latest);
    }
    return result;
  }, [events, sessionCatalog]);

  const visibleSessionTypes = useMemo(() => {
    const enabled = new Set(sessionTypes.map((type) => type.code));
    return sessionCatalog.filter((type) => enabled.has(type.code) || activeByCode.has(type.code));
  }, [activeByCode, sessionCatalog, sessionTypes]);

  async function toggle(type: EventType) {
    const active = activeByCode.get(type.code);
    setBusyCode(type.code);
    setError(null);
    try {
      await createEvent({
        dog_id: dogId,
        event_type_id: type.id,
        state: active ? "END" : "START",
        location: "NOT_APPLICABLE",
        option_id: null,
        numeric_value: null,
        unit: null,
        severity: null,
        notes: null,
        entry_method: "QUICK_LOG",
      });
      setEvents(await fetchSessionEvents());
      onEventSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update session.");
    } finally {
      setBusyCode(null);
    }
  }

  if (!visibleSessionTypes.length) return null;

  return (
    <section className="session-panel">
      <div className="section-heading">
        <div><p className="eyebrow">Active sessions</p><h2>Track duration</h2><p className="section-subcopy">Start once, then end when the activity finishes. Timers survive navigation and reloads.</p></div>
      </div>
      {error && <p className="event-error">{error}</p>}
      <div className="session-grid">
        {visibleSessionTypes.map((type) => {
          const active = activeByCode.get(type.code);
          return (
            <article className={`session-card ${active ? "active" : ""}`} key={type.code}>
              <div className="session-card-main">
                <span className="session-icon">{SESSION_ICONS[type.code] ?? "⏱️"}</span>
                <div>
                  <strong>{type.display_name}</strong>
                  {active ? (
                    <>
                      <span className="session-duration">{durationLabel(active.event_time, nowMs)}</span>
                      <small>Started {new Date(active.event_time).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}</small>
                    </>
                  ) : <small>Not active</small>}
                </div>
              </div>
              <button
                className={active ? "end-session-button" : "start-session-button"}
                disabled={busyCode === type.code}
                type="button"
                onClick={() => void toggle(type)}
              >
                {busyCode === type.code ? "Saving…" : active ? `End ${type.display_name}` : `Start ${type.display_name}`}
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}
