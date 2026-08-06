import { useEffect, useState } from "react";

import {
  getEvents,
  getObservationPeriods,
  getStatPreferences,
} from "../services/api";
import type { LoggedEvent } from "../types/event";
import type { ObservationPeriod } from "../types/observation";
import { InsightsCharts } from "./InsightsCharts";
import type { StatPreference } from "../types/stats";

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
): number {
  const relevant = [...events]
    .filter(
      (event) =>
        event.event_type_code === code &&
        event.state,
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

function calculate(
  code: string,
  events: LoggedEvent[],
  periods: ObservationPeriod[],
  startTime: string,
  endTime: string,
  isToday: boolean,
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
        detail: "pees logged",
      };
    }

    case "POOP_COUNT": {
      const value = count(events, "POOP");

      return {
        value: String(value),
        rawValue: value,
        comparisonGoal: "NEUTRAL",
        comparisonFormat: "COUNT",
        detail: "poops logged",
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
        detail: "potty accidents",
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
        return {
          value: String(count(events, "PEE")),
          detail: "pees during range",
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
        return {
          value: String(count(events, "POOP")),
          detail: "poops during range",
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
        events,
        "SLEEP",
      );

      return {
        value: minutesLabel(minutes),
        rawValue: minutes,
        comparisonGoal: "NEUTRAL",
        comparisonFormat: "MINUTES",
        detail: "completed naps",
      };
    }

    case "SLEEP_DURATION": {
      const minutes = completedDuration(
        events,
        "SLEEP_NIGHT",
      );

      return {
        value: minutesLabel(minutes),
        rawValue: minutes,
        comparisonGoal: "NEUTRAL",
        comparisonFormat: "MINUTES",
        detail: "completed nighttime sleep",
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
}: Props) {
  const [events, setEvents] =
    useState<LoggedEvent[]>([]);

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

        const [
          eventResults,
          periodResults,
          preferenceResults,
          previousEventResults,
          previousPeriodResults,
        ] = await Promise.all([
          currentEventsRequest,
          currentPeriodsRequest,
          preferencesRequest,
          previousEventsRequest,
          previousPeriodsRequest,
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

  return (
    <section className="dashboard-section">
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            {rangeLabel}
          </p>

          <h1>Insights</h1>

          <p>
            Stats reflect the selected period
            and only the activities you have
            chosen to track.
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
                  {
                    preference.display_name
                  }
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
        />
      )}
    </section>
  );
}