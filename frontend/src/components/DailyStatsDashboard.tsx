import { useEffect, useMemo, useState } from "react";

import { getEvents, getObservationPeriods, getStatPreferences } from "../services/api";
import type { LoggedEvent } from "../types/event";
import type { ObservationPeriod } from "../types/observation";
import type { StatPreference } from "../types/stats";
import { getLocalDayRange } from "../utils/date";

interface Props {
  dogId: string;
  refreshKey: number;
  preferenceRefreshKey: number;
}

interface StatValue {
  value: string;
  detail?: string;
}

function count(events: LoggedEvent[], code: string): number {
  return events.filter((event) => event.event_type_code === code).length;
}

function elapsedLabel(timestamp?: string): string {
  if (!timestamp) return "No log today";
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(timestamp).getTime()) / 60000));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder ? `${hours} hr ${remainder} min` : `${hours} hr`;
}

function minutesLabel(totalMinutes: number): string {
  const rounded = Math.max(0, Math.round(totalMinutes));
  const hours = Math.floor(rounded / 60);
  const minutes = rounded % 60;
  if (!hours) return `${minutes} min`;
  return minutes ? `${hours} hr ${minutes} min` : `${hours} hr`;
}

function completedDuration(events: LoggedEvent[], code: string): number {
  const relevant = [...events]
    .filter((event) => event.event_type_code === code && event.state)
    .sort((a, b) => new Date(a.event_time).getTime() - new Date(b.event_time).getTime());
  let start: Date | null = null;
  let minutes = 0;
  for (const event of relevant) {
    if (event.state === "START") start = new Date(event.event_time);
    if (event.state === "END" && start) {
      minutes += Math.max(0, (new Date(event.event_time).getTime() - start.getTime()) / 60000);
      start = null;
    }
  }
  return minutes;
}

function unobservedMinutes(periods: ObservationPeriod[], dayEnd: string): number {
  return periods.reduce((total, period) => {
    const end = period.end_time ? new Date(period.end_time) : new Date(Math.min(Date.now(), new Date(dayEnd).getTime()));
    return total + Math.max(0, (end.getTime() - new Date(period.start_time).getTime()) / 60000);
  }, 0);
}

function calculate(code: string, events: LoggedEvent[], periods: ObservationPeriod[], dayEnd: string): StatValue {
  const potty = events.filter((event) => ["PEE", "POOP"].includes(event.event_type_code));
  switch (code) {
    case "PEE_COUNT": return { value: String(count(events, "PEE")), detail: "logged today" };
    case "POOP_COUNT": return { value: String(count(events, "POOP")), detail: "logged today" };
    case "ACCIDENT_COUNT": return { value: String(potty.filter((event) => event.option_name?.toLowerCase() === "accident").length), detail: "potty accidents" };
    case "POTTY_SUCCESS_RATE": {
      if (!potty.length) return { value: "—", detail: "No potty logs yet" };
      const outside = potty.filter((event) => event.option_name?.toLowerCase() === "outside").length;
      return { value: `${Math.round((outside / potty.length) * 100)}%`, detail: `${outside} of ${potty.length} outside` };
    }
    case "SINCE_LAST_PEE": return { value: elapsedLabel(events.find((event) => event.event_type_code === "PEE")?.event_time), detail: "since latest pee" };
    case "SINCE_LAST_POOP": return { value: elapsedLabel(events.find((event) => event.event_type_code === "POOP")?.event_time), detail: "since latest poop" };
    case "NAP_DURATION": return { value: minutesLabel(completedDuration(events, "SLEEP")), detail: "completed naps" };
    case "SLEEP_DURATION": return { value: minutesLabel(completedDuration(events, "SLEEP_NIGHT")), detail: "completed sleep" };
    case "MEAL_COUNT": return { value: String(count(events, "MEAL")), detail: "meals logged" };
    case "TREAT_COUNT": return { value: String(count(events, "TREAT")), detail: "treats logged" };
    case "WALK_DISTANCE": {
      const walks = events.filter((event) => event.event_type_code === "WALK" && event.numeric_value);
      const miles = walks.reduce((sum, event) => sum + (event.unit === "kilometers" ? Number(event.numeric_value) * 0.621371 : Number(event.numeric_value)), 0);
      return { value: `${miles.toFixed(miles < 10 ? 1 : 0)} mi`, detail: "logged walk distance" };
    }
    case "SYMPTOM_COUNT": return { value: String(count(events, "SYMPTOM")), detail: "symptoms logged" };
    case "AVG_SYMPTOM_SEVERITY": {
      const values = events.filter((event) => event.event_type_code === "SYMPTOM" && event.severity).map((event) => event.severity as number);
      return values.length ? { value: `${(values.reduce((a, b) => a + b, 0) / values.length).toFixed(1)}/10`, detail: "average severity" } : { value: "—", detail: "No severity data" };
    }
    case "BEHAVIOR_COUNT": return { value: String(count(events, "BEHAVIOR")), detail: "behavior logs" };
    case "SOCIAL_COUNT": return { value: String(count(events, "SOCIAL")), detail: "social activities" };
    case "MEDICATION_COUNT": return { value: String(count(events, "MEDICATION")), detail: "medications logged" };
    case "UNOBSERVED_TIME": return { value: minutesLabel(unobservedMinutes(periods, dayEnd)), detail: "not directly observed" };
    default: return { value: "—" };
  }
}

export function DailyStatsDashboard({ dogId, refreshKey, preferenceRefreshKey }: Props) {
  const [events, setEvents] = useState<LoggedEvent[]>([]);
  const [periods, setPeriods] = useState<ObservationPeriod[]>([]);
  const [preferences, setPreferences] = useState<StatPreference[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { start, end } = useMemo(() => getLocalDayRange(), [refreshKey]);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true); setError(null);
      try {
        const [eventResults, periodResults, preferenceResults] = await Promise.all([
          getEvents(dogId, start, end, controller.signal),
          getObservationPeriods(dogId, start, end, false, controller.signal),
          getStatPreferences(dogId, controller.signal),
        ]);
        setEvents(eventResults); setPeriods(periodResults); setPreferences(preferenceResults);
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") setError(err.message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [dogId, refreshKey, preferenceRefreshKey, start, end]);

  const enabled = [...preferences]
    .filter((item) => item.is_enabled)
    .sort((a, b) => a.display_order - b.display_order);

  return (
    <section className="dashboard-section">
      <div className="page-heading">
        <div><p className="eyebrow">Today</p><h1>Daily insights</h1><p>Stats reflect only the activities you have chosen to track.</p></div>
      </div>
      {loading && <p className="status-message">Calculating today’s stats…</p>}
      {error && <p className="event-error">{error}</p>}
      {!loading && !error && enabled.length === 0 && <div className="empty-card"><p>No dashboard cards are enabled.</p><a href="#settings">Choose stats in Settings</a></div>}
      <div className="stats-grid">
        {enabled.map((preference) => {
          const stat = calculate(preference.code, events, periods, end);
          return <article className="stat-card" key={preference.code}><p>{preference.display_name}</p><strong>{stat.value}</strong>{stat.detail && <span>{stat.detail}</span>}</article>;
        })}
      </div>
    </section>
  );
}
