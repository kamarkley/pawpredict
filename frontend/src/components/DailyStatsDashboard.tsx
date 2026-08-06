import { useEffect, useState } from "react";

import {
  getEvents,
  getObservationPeriods,
  getStatPreferences,
} from "../services/api";
import type { LoggedEvent } from "../types/event";
import type { ObservationPeriod } from "../types/observation";
import type { StatPreference } from "../types/stats";

interface Props {
  dogId: string;
  startTime: string;
  endTime: string;
  rangeLabel: string;
  refreshKey: number;
  preferenceRefreshKey: number;
}

interface StatValue {
  value: string;
  detail?: string;
}

function count(events: LoggedEvent[], code: string): number {
  return events.filter(
    (event) => event.event_type_code === code,
  ).length;
}

function minutesLabel(totalMinutes: number): string {
  const rounded = Math.max(0, Math.round(totalMinutes));
  const hours = Math.floor(rounded / 60);
  const minutes = rounded % 60;

  if (!hours) {
    return `${minutes} min`;
  }

  return minutes
    ? `${hours} hr ${minutes} min`
    : `${hours} hr`;
}

function completedDuration(
  events: LoggedEvent[],
  code: string,
): number {
  const relevant = [...events]
    .filter(
      (event) =>
        event.event_type_code === code && event.state,
    )
    .sort(
      (a, b) =>
        new Date(a.event_time).getTime() -
        new Date(b.event_time).getTime(),
    );

  let start: Date | null = null;
  let minutes = 0;

  for (const event of relevant) {
    if (event.state === "START") {
      start = new Date(event.event_time);
    }

    if (event.state === "END" && start) {
      minutes += Math.max(
        0,
        (new Date(event.event_time).getTime() -
          start.getTime()) /
          60_000,
      );

      start = null;
    }
  }

  return minutes;
}

function unobservedMinutes(
  periods: ObservationPeriod[],
  rangeStart: string,
  rangeEnd: string,
): number {
  const rangeStartTime = new Date(rangeStart).getTime();
  const rangeEndTime = new Date(rangeEnd).getTime();

  return periods.reduce((total, period) => {
    const periodStart = new Date(period.start_time).getTime();

    const periodEnd = period.end_time
      ? new Date(period.end_time).getTime()
      : Date.now();

    const clippedStart = Math.max(
      periodStart,
      rangeStartTime,
    );

    const clippedEnd = Math.min(periodEnd, rangeEndTime);

    return (
      total +
      Math.max(0, (clippedEnd - clippedStart) / 60_000)
    );
  }, 0);
}

function elapsedLabel(timestamp?: string): string {
  if (!timestamp) {
    return "No log in range";
  }

  const minutes = Math.max(
    0,
    Math.floor(
      (Date.now() - new Date(timestamp).getTime()) / 60_000,
    ),
  );

  if (minutes < 60) {
    return `${minutes} min`;
  }

  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;

  return remainder
    ? `${hours} hr ${remainder} min`
    : `${hours} hr`;
}

function calculate(
  code: string,
  events: LoggedEvent[],
  periods: ObservationPeriod[],
  startTime: string,
  endTime: string,
  isToday: boolean,
): StatValue {
  const potty = events.filter((event) =>
    ["PEE", "POOP"].includes(event.event_type_code),
  );

  switch (code) {
    case "PEE_COUNT":
      return {
        value: String(count(events, "PEE")),
        detail: "pees logged",
      };

    case "POOP_COUNT":
      return {
        value: String(count(events, "POOP")),
        detail: "poops logged",
      };

    case "ACCIDENT_COUNT":
      return {
        value: String(
          potty.filter(
            (event) =>
              event.option_name?.toLowerCase() ===
              "accident",
          ).length,
        ),
        detail: "potty accidents",
      };

    case "POTTY_SUCCESS_RATE": {
      if (!potty.length) {
        return {
          value: "—",
          detail: "No potty logs in range",
        };
      }

      const outside = potty.filter(
        (event) =>
          event.option_name?.toLowerCase() === "outside",
      ).length;

      return {
        value: `${Math.round(
          (outside / potty.length) * 100,
        )}%`,
        detail: `${outside} of ${potty.length} outside`,
      };
    }

    case "SINCE_LAST_PEE": {
      if (!isToday) {
        return {
          value: String(count(events, "PEE")),
          detail: "pees during range",
        };
      }

      return {
        value: elapsedLabel(
          events.find(
            (event) => event.event_type_code === "PEE",
          )?.event_time,
        ),
        detail: "since latest pee",
      };
    }

    case "SINCE_LAST_POOP": {
      if (!isToday) {
        return {
          value: String(count(events, "POOP")),
          detail: "poops during range",
        };
      }

      return {
        value: elapsedLabel(
          events.find(
            (event) => event.event_type_code === "POOP",
          )?.event_time,
        ),
        detail: "since latest poop",
      };
    }

    case "NAP_DURATION":
      return {
        value: minutesLabel(
          completedDuration(events, "SLEEP"),
        ),
        detail: "completed naps",
      };

    case "SLEEP_DURATION":
      return {
        value: minutesLabel(
          completedDuration(events, "SLEEP_NIGHT"),
        ),
        detail: "completed nighttime sleep",
      };

    case "MEAL_COUNT":
      return {
        value: String(count(events, "MEAL")),
        detail: "meals logged",
      };

    case "TREAT_COUNT":
      return {
        value: String(count(events, "TREAT")),
        detail: "treats logged",
      };

    case "WALK_DISTANCE": {
      const walks = events.filter(
        (event) =>
          event.event_type_code === "WALK" &&
          event.numeric_value,
      );

      const miles = walks.reduce((sum, event) => {
        const value = Number(event.numeric_value);

        return (
          sum +
          (event.unit === "kilometers"
            ? value * 0.621371
            : value)
        );
      }, 0);

      return {
        value: `${miles.toFixed(miles < 10 ? 1 : 0)} mi`,
        detail: "logged walk distance",
      };
    }

    case "SYMPTOM_COUNT":
      return {
        value: String(count(events, "SYMPTOM")),
        detail: "symptoms logged",
      };

    case "AVG_SYMPTOM_SEVERITY": {
      const values = events
        .filter(
          (event) =>
            event.event_type_code === "SYMPTOM" &&
            event.severity,
        )
        .map((event) => event.severity as number);

      if (!values.length) {
        return {
          value: "—",
          detail: "No severity data",
        };
      }

      return {
        value: `${(
          values.reduce((a, b) => a + b, 0) /
          values.length
        ).toFixed(1)}/10`,
        detail: "average severity",
      };
    }

    case "BEHAVIOR_COUNT":
      return {
        value: String(count(events, "BEHAVIOR")),
        detail: "behavior logs",
      };

    case "SOCIAL_COUNT":
      return {
        value: String(count(events, "SOCIAL")),
        detail: "social activities",
      };

    case "MEDICATION_COUNT":
      return {
        value: String(count(events, "MEDICATION")),
        detail: "medications logged",
      };

    case "UNOBSERVED_TIME":
      return {
        value: minutesLabel(
          unobservedMinutes(
            periods,
            startTime,
            endTime,
          ),
        ),
        detail: "not directly observed",
      };

    default:
      return { value: "—" };
  }
}

export function DailyStatsDashboard({
  dogId,
  startTime,
  endTime,
  rangeLabel,
  refreshKey,
  preferenceRefreshKey,
}: Props) {
  const [events, setEvents] = useState<LoggedEvent[]>([]);
  const [periods, setPeriods] = useState<
    ObservationPeriod[]
  >([]);
  const [preferences, setPreferences] = useState<
    StatPreference[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const [
          eventResults,
          periodResults,
          preferenceResults,
        ] = await Promise.all([
          getEvents(
            dogId,
            startTime,
            endTime,
            controller.signal,
          ),
          getObservationPeriods(
            dogId,
            startTime,
            endTime,
            false,
            controller.signal,
          ),
          getStatPreferences(dogId, controller.signal),
        ]);

        setEvents(eventResults);
        setPeriods(periodResults);
        setPreferences(preferenceResults);
      } catch (err) {
        if (
          err instanceof Error &&
          err.name !== "AbortError"
        ) {
          setError(err.message);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => controller.abort();
  }, [
    dogId,
    startTime,
    endTime,
    refreshKey,
    preferenceRefreshKey,
  ]);

  const enabled = [...preferences]
    .filter((item) => item.is_enabled)
    .sort(
      (a, b) => a.display_order - b.display_order,
    );

  const todayRange = (() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    return (
      new Date(startTime).getTime() === today.getTime() &&
      new Date(endTime).getTime() === tomorrow.getTime()
    );
  })();

  return (
    <section className="dashboard-section">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{rangeLabel}</p>
          <h1>Insights</h1>
          <p>
            Stats reflect the selected period and only the
            activities you have chosen to track.
          </p>
        </div>
      </div>

      {loading && (
        <p className="status-message">
          Calculating insights…
        </p>
      )}

      {error && (
        <p className="event-error">{error}</p>
      )}

      {!loading && !error && enabled.length === 0 && (
        <div className="empty-card">
          <p>No dashboard cards are enabled.</p>
          <a href="#settings">Choose stats in Settings</a>
        </div>
      )}

      <div className="stats-grid">
        {enabled.map((preference) => {
          const stat = calculate(
            preference.code,
            events,
            periods,
            startTime,
            endTime,
            todayRange,
          );

          return (
            <article
              className="stat-card"
              key={preference.code}
            >
              <p>{preference.display_name}</p>
              <strong>{stat.value}</strong>
              {stat.detail && <span>{stat.detail}</span>}
            </article>
          );
        })}
      </div>
    </section>
  );
}