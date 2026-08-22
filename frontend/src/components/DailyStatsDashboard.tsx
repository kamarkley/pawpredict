import { useEffect, useState } from "react";

import {
  getChartPreferences,
  getEvents,
  getObservationPeriods,
  getStatPreferences,
  getUIPreferences,
} from "../services/api";
import type { LoggedEvent } from "../types/event";
import type { ObservationPeriod } from "../types/observation";
import { InsightsCharts } from "./InsightsCharts";
import type { StatPreference } from "../types/stats";
import type { ChartPreference } from "../types/dashboard";

interface Props {
  dogId: string;
  startTime: string;
  endTime: string;
  rangeLabel: string;
  previousStartTime: string | null;
  previousEndTime: string | null;
  comparisonLabel: string | null;
  refreshKey: number;
  preferenceRefreshKey: number;
  embedded?: boolean;
}

type ComparisonGoal = "HIGHER" | "LOWER" | "NEUTRAL";

type ComparisonFormat =
  | "COUNT"
  | "PERCENTAGE_POINT"
  | "MINUTES"
  | "DISTANCE"
  | "DECIMAL";

interface StatValue {
  value: string;
  detail?: string;
  rawValue?: number;
  comparisonGoal?: ComparisonGoal;
  comparisonFormat?: ComparisonFormat;
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
  rangeStart: string,
  rangeEnd: string,
): number {
  const relevant = [...events]
    .filter((event) => event.event_type_code === code && event.state)
    .sort((a, b) => new Date(a.event_time).getTime() - new Date(b.event_time).getTime());
  const clipStart = new Date(rangeStart).getTime();
  const clipEnd = new Date(rangeEnd).getTime();
  let startTime: number | null = null;
  let minutes = 0;
  for (const event of relevant) {
    const t = new Date(event.event_time).getTime();
    if (event.state === "START") startTime = t;
    if (event.state === "END" && startTime !== null) {
      const overlapStart = Math.max(startTime, clipStart);
      const overlapEnd = Math.min(t, clipEnd);
      if (overlapEnd > overlapStart) minutes += (overlapEnd - overlapStart) / 60_000;
      startTime = null;
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
    const periodStart = new Date(
      period.start_time,
    ).getTime();

    const periodEnd = period.end_time
      ? new Date(period.end_time).getTime()
      : Date.now();

    const clippedStart = Math.max(
      periodStart,
      rangeStartTime,
    );

    const clippedEnd = Math.min(
      periodEnd,
      rangeEndTime,
    );

    return (
      total +
      Math.max(
        0,
        (clippedEnd - clippedStart) / 60_000,
      )
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
      (Date.now() -
        new Date(timestamp).getTime()) /
        60_000,
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

function averageIntervalMinutes(
  events: LoggedEvent[],
  eventCode: "PEE" | "POOP",
): number | null {
  const times = events
    .filter((event) => event.event_type_code === eventCode)
    .map((event) => new Date(event.event_time).getTime())
    .sort((a, b) => a - b);

  if (times.length < 2) return null;

  const intervals = times.slice(1).map((time, index) => (time - times[index]) / 60_000);
  return intervals.reduce((sum, value) => sum + value, 0) / intervals.length;
}

function peakEventWindow(
  events: LoggedEvent[],
  eventCode: "PEE" | "POOP",
): string {
  const relevant = events.filter((event) => event.event_type_code === eventCode);
  if (!relevant.length) return "—";
  const counts = new Map<number, number>();
  for (const event of relevant) {
    const hour = new Date(event.event_time).getHours();
    counts.set(hour, (counts.get(hour) ?? 0) + 1);
  }
  const hour = [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0];
  const start = new Date();
  start.setHours(hour, 0, 0, 0);
  const end = new Date(start);
  end.setHours(hour + 1);
  return `${start.toLocaleTimeString("en-US", { hour: "numeric" })}–${end.toLocaleTimeString("en-US", { hour: "numeric" })}`;
}

function statDisplayName(code: string, fallback: string, isToday: boolean): string {
  if (isToday) return fallback;
  const names: Record<string, string> = {
    PEE_COUNT: "Total pees",
    POOP_COUNT: "Total poops",
    ACCIDENT_COUNT: "Total accidents",
    POTTY_SUCCESS_RATE: "Potty success rate",
    SINCE_LAST_PEE: "Average time between pees",
    SINCE_LAST_POOP: "Average time between poops",
    NAP_DURATION: "Total nap time",
    SLEEP_DURATION: "Total night sleep",
    MEAL_COUNT: "Meals logged",
    TREAT_COUNT: "Treats logged",
    WALK_DISTANCE: "Walk distance",
    SYMPTOM_COUNT: "Symptoms logged",
    AVG_SYMPTOM_SEVERITY: "Average symptom severity",
    BEHAVIOR_COUNT: "Behavior logs",
    SOCIAL_COUNT: "Social activities",
    MEDICATION_COUNT: "Medications logged",
    UNOBSERVED_TIME: "Unobserved time",
  };
  return names[code] ?? fallback;
}

function calculate(
  code: string,
  events: LoggedEvent[],
  periods: ObservationPeriod[],
  startTime: string,
  endTime: string,
  isToday: boolean,
  sessionEvents: LoggedEvent[] = events,
): StatValue {
  const potty = events.filter((event) =>
    ["PEE", "POOP"].includes(
      event.event_type_code,
    ),
  );

  switch (code) {
    case "PEE_COUNT": {
      const value = count(events, "PEE");

      return {
        value: String(value),
        rawValue: value,
        comparisonGoal: "NEUTRAL",
        comparisonFormat: "COUNT",
        detail: isToday ? "pees today" : "total pees in range",
      };
    }

    case "POOP_COUNT": {
      const value = count(events, "POOP");

      return {
        value: String(value),
        rawValue: value,
        comparisonGoal: "NEUTRAL",
        comparisonFormat: "COUNT",
        detail: isToday ? "poops today" : "total poops in range",
      };
    }

    case "ACCIDENT_COUNT": {
      const value = potty.filter(
        (event) =>
          event.option_name?.toLowerCase() ===
          "accident",
      ).length;

      return {
        value: String(value),
        rawValue: value,
        comparisonGoal: "LOWER",
        comparisonFormat: "COUNT",
        detail: isToday ? "accidents today" : "accidents in range",
      };
    }

    case "POTTY_SUCCESS_RATE": {
      if (!potty.length) {
        return {
          value: "—",
          detail: "No potty logs in range",
        };
      }

      const outside = potty.filter(
        (event) =>
          event.option_name?.toLowerCase() ===
          "outside",
      ).length;

      const rate =
        (outside / potty.length) * 100;

      return {
        value: `${Math.round(rate)}%`,
        rawValue: rate,
        comparisonGoal: "HIGHER",
        comparisonFormat:
          "PERCENTAGE_POINT",
        detail: `${outside} of ${potty.length} outside`,
      };
    }

    case "SINCE_LAST_PEE": {
      if (!isToday) {
        const interval = averageIntervalMinutes(events, "PEE");
        return interval === null
          ? { value: "—", detail: "Need at least two pee logs" }
          : {
              value: minutesLabel(interval),
              rawValue: interval,
              comparisonGoal: "NEUTRAL",
              comparisonFormat: "MINUTES",
              detail: "average gap between exact pee logs",
            };
      }

      return {
        value: elapsedLabel(
          events.find(
            (event) =>
              event.event_type_code === "PEE",
          )?.event_time,
        ),
        detail: "since latest pee",
      };
    }

    case "SINCE_LAST_POOP": {
      if (!isToday) {
        const interval = averageIntervalMinutes(events, "POOP");
        return interval === null
          ? { value: "—", detail: "Need at least two poop logs" }
          : {
              value: minutesLabel(interval),
              rawValue: interval,
              comparisonGoal: "NEUTRAL",
              comparisonFormat: "MINUTES",
              detail: "average gap between exact poop logs",
            };
      }

      return {
        value: elapsedLabel(
          events.find(
            (event) =>
              event.event_type_code === "POOP",
          )?.event_time,
        ),
        detail: "since latest poop",
      };
    }

    case "NAP_DURATION": {
      const minutes = completedDuration(
        sessionEvents,
        "SLEEP",
        startTime,
        endTime,
      );

      return {
        value: minutesLabel(minutes),
        rawValue: minutes,
        comparisonGoal: "NEUTRAL",
        comparisonFormat: "MINUTES",
        detail: isToday ? "nap time today" : "nap time in range",
      };
    }

    case "SLEEP_DURATION": {
      const minutes = completedDuration(
        sessionEvents,
        "SLEEP_NIGHT",
        startTime,
        endTime,
      );

      return {
        value: minutesLabel(minutes),
        rawValue: minutes,
        comparisonGoal: "NEUTRAL",
        comparisonFormat: "MINUTES",
        detail: isToday ? "night sleep today" : "night sleep in range",
      };
    }

    case "MEAL_COUNT": {
      const value = count(events, "MEAL");

      return {
        value: String(value),
        rawValue: value,
        comparisonGoal: "NEUTRAL",
        comparisonFormat: "COUNT",
        detail: "meals logged",
      };
    }

    case "TREAT_COUNT": {
      const value = count(events, "TREAT");

      return {
        value: String(value),
        rawValue: value,
        comparisonGoal: "NEUTRAL",
        comparisonFormat: "COUNT",
        detail: "treats logged",
      };
    }

    case "WALK_DISTANCE": {
      const walks = events.filter(
        (event) =>
          event.event_type_code === "WALK" &&
          event.numeric_value,
      );

      const miles = walks.reduce(
        (sum, event) => {
          const value = Number(
            event.numeric_value,
          );

          return (
            sum +
            (event.unit === "kilometers"
              ? value * 0.621371
              : value)
          );
        },
        0,
      );

      return {
        value: `${miles.toFixed(
          miles < 10 ? 1 : 0,
        )} mi`,
        rawValue: miles,
        comparisonGoal: "NEUTRAL",
        comparisonFormat: "DISTANCE",
        detail: "logged walk distance",
      };
    }

    case "SYMPTOM_COUNT": {
      const value = count(
        events,
        "SYMPTOM",
      );

      return {
        value: String(value),
        rawValue: value,
        comparisonGoal: "LOWER",
        comparisonFormat: "COUNT",
        detail: "symptoms logged",
      };
    }

    case "AVG_SYMPTOM_SEVERITY": {
      const values = events
        .filter(
          (event) =>
            event.event_type_code ===
              "SYMPTOM" &&
            event.severity,
        )
        .map(
          (event) =>
            event.severity as number,
        );

      if (!values.length) {
        return {
          value: "—",
          detail: "No severity data",
        };
      }

      const average =
        values.reduce(
          (a, b) => a + b,
          0,
        ) / values.length;

      return {
        value: `${average.toFixed(1)}/10`,
        rawValue: average,
        comparisonGoal: "LOWER",
        comparisonFormat: "DECIMAL",
        detail: "average severity",
      };
    }

    case "BEHAVIOR_COUNT": {
      const value = count(
        events,
        "BEHAVIOR",
      );

      return {
        value: String(value),
        rawValue: value,
        comparisonGoal: "NEUTRAL",
        comparisonFormat: "COUNT",
        detail: "behavior logs",
      };
    }

    case "SOCIAL_COUNT": {
      const value = count(
        events,
        "SOCIAL",
      );

      return {
        value: String(value),
        rawValue: value,
        comparisonGoal: "NEUTRAL",
        comparisonFormat: "COUNT",
        detail: "social activities",
      };
    }

    case "MEDICATION_COUNT": {
      const value = count(
        events,
        "MEDICATION",
      );

      return {
        value: String(value),
        rawValue: value,
        comparisonGoal: "NEUTRAL",
        comparisonFormat: "COUNT",
        detail: "medications logged",
      };
    }

    case "UNOBSERVED_TIME": {
      const minutes = unobservedMinutes(
        periods,
        startTime,
        endTime,
      );

      return {
        value: minutesLabel(minutes),
        rawValue: minutes,
        comparisonGoal: "NEUTRAL",
        comparisonFormat: "MINUTES",
        detail: "not directly observed",
      };
    }

    default:
      return {
        value: "—",
      };
  }
}

function formatComparisonAmount(
  amount: number,
  format: ComparisonFormat,
): string {
  const absolute = Math.abs(amount);

  switch (format) {
    case "PERCENTAGE_POINT":
      return `${absolute.toFixed(0)} pp`;

    case "MINUTES":
      return minutesLabel(absolute);

    case "DISTANCE":
      return `${absolute.toFixed(1)} mi`;

    case "DECIMAL":
      return absolute.toFixed(1);

    case "COUNT":
    default:
      return String(
        Math.round(absolute),
      );
  }
}

function buildComparison(
  current: StatValue,
  previous: StatValue,
  comparisonLabel: string | null,
): {
  text: string;
  className: string;
} | null {
  if (
    comparisonLabel === null ||
    current.rawValue === undefined ||
    previous.rawValue === undefined ||
    current.comparisonFormat === undefined
  ) {
    return null;
  }

  const difference =
    current.rawValue -
    previous.rawValue;

  if (Math.abs(difference) < 0.001) {
    return {
      text: `No change from ${comparisonLabel.toLowerCase()}`,
      className: "comparison-neutral",
    };
  }

  const amount = formatComparisonAmount(
    difference,
    current.comparisonFormat,
  );

  const arrow =
    difference > 0 ? "↑" : "↓";

  let className =
    "comparison-neutral";

  if (
    current.comparisonGoal === "HIGHER"
  ) {
    className =
      difference > 0
        ? "comparison-positive"
        : "comparison-negative";
  }

  if (
    current.comparisonGoal === "LOWER"
  ) {
    className =
      difference < 0
        ? "comparison-positive"
        : "comparison-negative";
  }

  return {
    text: `${arrow} ${amount} vs ${comparisonLabel.toLowerCase()}`,
    className,
  };
}

function rangeDayCount(
  startTime: string,
  endTime: string,
): number {
  const duration =
    new Date(endTime).getTime() -
    new Date(startTime).getTime();

  return Math.max(
    1,
    Math.round(
      duration / 86_400_000,
    ),
  );
}

function busiestHour(
  events: LoggedEvent[],
): string {
  if (!events.length) {
    return "No activity yet";
  }

  const counts = new Map<
    number,
    number
  >();

  for (const event of events) {
    const hour = new Date(
      event.event_time,
    ).getHours();

    counts.set(
      hour,
      (counts.get(hour) ?? 0) + 1,
    );
  }

  const [hour] = [
    ...counts.entries(),
  ].sort(
    (a, b) => b[1] - a[1],
  )[0];

  const start = new Date();
  start.setHours(hour, 0, 0, 0);

  const end = new Date(start);
  end.setHours(
    end.getHours() + 1,
  );

  const startLabel =
    start.toLocaleTimeString(
      "en-US",
      {
        hour: "numeric",
      },
    );

  const endLabel =
    end.toLocaleTimeString(
      "en-US",
      {
        hour: "numeric",
      },
    );

  return `${startLabel}–${endLabel}`;
}

function mostLoggedActivity(
  events: LoggedEvent[],
): string {
  if (!events.length) {
    return "No activity yet";
  }

  const counts = new Map<
    string,
    {
      name: string;
      count: number;
    }
  >();

  for (const event of events) {
    const existing = counts.get(
      event.event_type_code,
    );

    counts.set(
      event.event_type_code,
      {
        name:
          event.event_type_name,
        count:
          (existing?.count ?? 0) +
          1,
      },
    );
  }

  const result = [
    ...counts.values(),
  ].sort(
    (a, b) => b.count - a.count,
  )[0];

  return `${result.name} · ${result.count}`;
}

export function DailyStatsDashboard({
  dogId,
  startTime,
  endTime,
  rangeLabel,
  previousStartTime,
  previousEndTime,
  comparisonLabel,
  refreshKey,
  preferenceRefreshKey,
  embedded = false,
}: Props) {
  const [events, setEvents] =
    useState<LoggedEvent[]>([]);

  const [sessionEvents, setSessionEvents] = useState<LoggedEvent[]>([]);
  const [previousSessionEvents, setPreviousSessionEvents] = useState<LoggedEvent[]>([]);

  const [periods, setPeriods] =
    useState<ObservationPeriod[]>(
      [],
    );

  const [
    previousEvents,
    setPreviousEvents,
  ] = useState<LoggedEvent[]>([]);

  const [
    previousPeriods,
    setPreviousPeriods,
  ] = useState<
    ObservationPeriod[]
  >([]);

  const [
    preferences,
    setPreferences,
  ] = useState<
    StatPreference[]
  >([]);

  const [loading, setLoading] =
    useState(true);

  const [chartPreferences, setChartPreferences] =
    useState<ChartPreference[]>([]);

  const [error, setError] =
    useState<string | null>(null);

  useEffect(() => {
    const controller =
      new AbortController();

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const currentEventsRequest =
          getEvents(
            dogId,
            startTime,
            endTime,
            controller.signal,
          );

        const currentPeriodsRequest =
          getObservationPeriods(
            dogId,
            startTime,
            endTime,
            false,
            controller.signal,
          );

        const preferencesRequest =
          getStatPreferences(
            dogId,
            controller.signal,
          );

        const previousEventsRequest =
          previousStartTime &&
          previousEndTime
            ? getEvents(
                dogId,
                previousStartTime,
                previousEndTime,
                controller.signal,
              )
            : Promise.resolve([]);

        const previousPeriodsRequest =
          previousStartTime &&
          previousEndTime
            ? getObservationPeriods(
                dogId,
                previousStartTime,
                previousEndTime,
                false,
                controller.signal,
              )
            : Promise.resolve([]);


        const sessionStart = new Date(new Date(startTime).getTime() - 36 * 60 * 60 * 1000).toISOString();
        const sessionEventsRequest = getEvents(dogId, sessionStart, endTime, controller.signal);
        const previousSessionEventsRequest = previousStartTime && previousEndTime
          ? getEvents(dogId, new Date(new Date(previousStartTime).getTime() - 36 * 60 * 60 * 1000).toISOString(), previousEndTime, controller.signal)
          : Promise.resolve([]);

        const [
          eventResults,
          periodResults,
          preferenceResults,
          previousEventResults,
          previousPeriodResults,
          chartPreferenceResults,
          uiPreferenceResults,
          sessionEventResults,
          previousSessionEventResults,
        ] = await Promise.all([
          currentEventsRequest,
          currentPeriodsRequest,
          preferencesRequest,
          previousEventsRequest,
          previousPeriodsRequest,

          getChartPreferences(
            dogId,
            controller.signal,
          ),

          getUIPreferences(
            dogId,
            controller.signal,
          ),
          sessionEventsRequest,
          previousSessionEventsRequest,
        ]);

        setEvents(
          eventResults,
        );

        setPeriods(
          periodResults,
        );

        setPreferences(
          preferenceResults,
        );

        setPreviousEvents(
          previousEventResults,
        );

        setPreviousPeriods(
          previousPeriodResults,
        );
        setSessionEvents(sessionEventResults);
        setPreviousSessionEvents(previousSessionEventResults);

        setChartPreferences(
          chartPreferenceResults,
        );

        document.documentElement.style.setProperty(
          "--paw-accent",
          uiPreferenceResults.accent_color,
        );    
      
      } catch (err) {
        if (
          err instanceof Error &&
          err.name !== "AbortError"
        ) {
          setError(
            err.message,
          );
        }
      } finally {
        if (
          !controller.signal.aborted
        ) {
          setLoading(false);
        }
      }
    }

    void load();

    return () =>
      controller.abort();
  }, [
    dogId,
    startTime,
    endTime,
    previousStartTime,
    previousEndTime,
    refreshKey,
    preferenceRefreshKey,
  ]);

  const enabled = [
    ...preferences,
  ]
    .filter(
      (item) => item.is_enabled,
    )
    .sort(
      (a, b) =>
        a.display_order -
        b.display_order,
    );

  const todayRange = (() => {
    const today = new Date();
    today.setHours(
      0,
      0,
      0,
      0,
    );

    const tomorrow =
      new Date(today);

    tomorrow.setDate(
      tomorrow.getDate() + 1,
    );

    return (
      new Date(
        startTime,
      ).getTime() ===
        today.getTime() &&
      new Date(
        endTime,
      ).getTime() ===
        tomorrow.getTime()
    );
  })();

  const days =
    rangeDayCount(
      startTime,
      endTime,
    );

  const averageEventsPerDay =
    events.length /
    Math.max(1, days);

  const rangeMinutes = Math.max(1, (new Date(endTime).getTime() - new Date(startTime).getTime()) / 60_000);
  const unobserved = unobservedMinutes(periods, startTime, endTime);
  const observedPercent = Math.max(0, Math.min(100, ((rangeMinutes - unobserved) / rangeMinutes) * 100));
  const intervalPottyEvidence = periods.filter((period) => period.peed_during || period.pooped_during).length;

  return (
    <section className="dashboard-section">
      <div className={embedded ? "embedded-insights-heading" : "page-heading"}>
        <div>
          <p className="eyebrow">{embedded ? "Daily insights" : rangeLabel}</p>
          {embedded ? <h2>{rangeLabel}</h2> : <h1>Insights</h1>}
          <p>
            {embedded
              ? "Stats and patterns for this calendar day."
              : "Stats reflect the selected period and only the activities you have chosen to track."}
          </p>
        </div>
      </div>

      {loading && (
        <p className="status-message">
          Calculating insights…
        </p>
      )}

      {error && (
        <p className="event-error">
          {error}
        </p>
      )}

      {!loading && !error && (
        <div className="insight-highlights">
          <article className="highlight-card">
            <span>Total events</span>
            <strong>
              {events.length}
            </strong>
            <p>
              activity logs in this period
            </p>
          </article>

          <article className="highlight-card">
            <span>
              Daily average
            </span>

            <strong>
              {averageEventsPerDay.toFixed(
                averageEventsPerDay <
                  10
                  ? 1
                  : 0,
              )}
            </strong>

            <p>
              events per day
            </p>
          </article>

          <article className="highlight-card">
            <span>
              Peak pee window
            </span>

            <strong>
              {peakEventWindow(events, "PEE")}
            </strong>

            <p>
              most common exact pee hour
            </p>
          </article>

          <article className="highlight-card">
            <span>
              Peak poop window
            </span>

            <strong>
              {peakEventWindow(events, "POOP")}
            </strong>

            <p>
              most common exact poop hour
            </p>
          </article>

          <article className="highlight-card">
            <span>
              Busiest hour
            </span>

            <strong>
              {busiestHour(
                events,
              )}
            </strong>

            <p>
              most frequently logged window
            </p>
          </article>

          <article className="highlight-card">
            <span>
              Top activity
            </span>

            <strong>
              {mostLoggedActivity(
                events,
              )}
            </strong>

            <p>
              most common event type
            </p>
          </article>

          <article className="highlight-card">
            <span>Observed coverage</span>
            <strong>{observedPercent.toFixed(0)}%</strong>
            <p>of this range has direct observation</p>
          </article>

          <article className="highlight-card">
            <span>Interval potty evidence</span>
            <strong>{intervalPottyEvidence}</strong>
            <p>unobserved windows with known pee/poop</p>
          </article>
        </div>
      )}

      {!loading &&
        !error &&
        enabled.length === 0 && (
          <div className="empty-card">
            <p>
              No dashboard cards are enabled.
            </p>

            <a href="#settings">
              Choose stats in Settings
            </a>
          </div>
        )}

      <div className="stats-grid">
        {enabled.map(
          (preference) => {
            const stat =
              calculate(
                preference.code,
                events,
                periods,
                startTime,
                endTime,
                todayRange,
                sessionEvents,
              );

            const previousStat =
              previousStartTime &&
              previousEndTime
                ? calculate(
                    preference.code,
                    previousEvents,
                    previousPeriods,
                    previousStartTime,
                    previousEndTime,
                    false,
                    previousSessionEvents,
                  )
                : null;

            const comparison =
              previousStat
                ? buildComparison(
                    stat,
                    previousStat,
                    comparisonLabel,
                  )
                : null;

            return (
              <article
                className="stat-card"
                key={
                  preference.code
                }
              >
                <p>
                  {statDisplayName(
                    preference.code,
                    preference.display_name,
                    todayRange,
                  )}
                </p>

                <strong>
                  {stat.value}
                </strong>

                {stat.detail && (
                  <span>
                    {stat.detail}
                  </span>
                )}

                {comparison && (
                  <small
                    className={
                      comparison.className
                    }
                  >
                    {
                      comparison.text
                    }
                  </small>
                )}
              </article>
            );
          },
        )}
      </div>

      {!loading && !error && (
        <InsightsCharts
          events={events}
          startTime={startTime}
          endTime={endTime}
          chartPreferences={chartPreferences}
          sessionEvents={sessionEvents}
        />
      )}
    </section>
  );
}