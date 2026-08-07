import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ChartPreference } from "../types/dashboard";
import type { LoggedEvent } from "../types/event";

interface Props {
  events: LoggedEvent[];
  startTime: string;
  endTime: string;
  chartPreferences: ChartPreference[];
}

interface DailyActivityPoint {
  date: string;
  events: number;
}

interface PottyPoint {
  outcome: string;
  count: number;
}

interface PottyHourPoint {
  hour: string;
  pee: number;
  poop: number;
}

interface AccidentPoint {
  date: string;
  accidents: number;
}

interface SleepPoint {
  date: string;
  naps: number;
  nighttime: number;
}

interface NapPoint {
  date: string;
  averageNap: number;
}

interface TimeOfDayPoint {
  period: string;
  events: number;
}

interface WalkPoint {
  date: string;
  miles: number;
}

interface BreakdownPoint {
  name: string;
  count: number;
}

interface SymptomPoint {
  date: string;
  severity: number;
}

function dateKey(
  timestamp: string,
): string {
  const date =
    new Date(timestamp);

  const year =
    date.getFullYear();

  const month = String(
    date.getMonth() + 1,
  ).padStart(2, "0");

  const day = String(
    date.getDate(),
  ).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function displayDate(
  dateString: string,
): string {
  const date =
    new Date(
      `${dateString}T00:00:00`,
    );

  return date.toLocaleDateString(
    "en-US",
    {
      month: "short",
      day: "numeric",
    },
  );
}

function getDatesInRange(
  startTime: string,
  endTime: string,
): string[] {
  const dates: string[] = [];

  const current =
    new Date(startTime);

  current.setHours(
    0,
    0,
    0,
    0,
  );

  const end =
    new Date(endTime);

  while (current < end) {
    const year =
      current.getFullYear();

    const month = String(
      current.getMonth() + 1,
    ).padStart(2, "0");

    const day = String(
      current.getDate(),
    ).padStart(2, "0");

    dates.push(
      `${year}-${month}-${day}`,
    );

    current.setDate(
      current.getDate() + 1,
    );
  }

  return dates;
}

function buildDailyActivity(
  events: LoggedEvent[],
  startTime: string,
  endTime: string,
): DailyActivityPoint[] {
  const counts =
    new Map<string, number>();

  for (const event of events) {
    const key =
      dateKey(event.event_time);

    counts.set(
      key,
      (counts.get(key) ?? 0) + 1,
    );
  }

  return getDatesInRange(
    startTime,
    endTime,
  ).map((date) => ({
    date: displayDate(date),
    events: counts.get(date) ?? 0,
  }));
}

function buildPottyOutcomes(
  events: LoggedEvent[],
): PottyPoint[] {
  const counts =
    new Map<string, number>();

  for (const event of events) {
    if (
      event.event_type_code !==
        "PEE" &&
      event.event_type_code !==
        "POOP"
    ) {
      continue;
    }

    const outcome =
      event.option_name?.trim() ||
      "Not specified";

    counts.set(
      outcome,
      (counts.get(outcome) ?? 0) +
        1,
    );
  }

  return [
    ...counts.entries(),
  ]
    .map(
      ([outcome, count]) => ({
        outcome,
        count,
      }),
    )
    .sort(
      (a, b) =>
        b.count - a.count,
    );
}

function hourLabel(
  hour: number,
): string {
  const date = new Date();

  date.setHours(
    hour,
    0,
    0,
    0,
  );

  return date.toLocaleTimeString(
    "en-US",
    {
      hour: "numeric",
    },
  );
}

function buildPottyByHour(
  events: LoggedEvent[],
): PottyHourPoint[] {
  const hours = Array.from(
    { length: 24 },
    (_, hour) => ({
      hour: hourLabel(hour),
      pee: 0,
      poop: 0,
    }),
  );

  for (const event of events) {
    const hour =
      new Date(
        event.event_time,
      ).getHours();

    if (
      event.event_type_code ===
      "PEE"
    ) {
      hours[hour].pee += 1;
    }

    if (
      event.event_type_code ===
      "POOP"
    ) {
      hours[hour].poop += 1;
    }
  }

  return hours;
}

function buildAccidentTrend(
  events: LoggedEvent[],
  startTime: string,
  endTime: string,
): AccidentPoint[] {
  const counts =
    new Map<string, number>();

  for (const event of events) {
    const potty =
      event.event_type_code ===
        "PEE" ||
      event.event_type_code ===
        "POOP";

    const accident =
      event.option_name
        ?.toLowerCase() ===
      "accident";

    if (!potty || !accident) {
      continue;
    }

    const key =
      dateKey(event.event_time);

    counts.set(
      key,
      (counts.get(key) ?? 0) + 1,
    );
  }

  return getDatesInRange(
    startTime,
    endTime,
  ).map((date) => ({
    date: displayDate(date),
    accidents:
      counts.get(date) ?? 0,
  }));
}

function calculateDailySleep(
  events: LoggedEvent[],
  code: string,
): Map<string, number> {
  const relevant = [
    ...events,
  ]
    .filter(
      (event) =>
        event.event_type_code ===
          code &&
        event.state,
    )
    .sort(
      (a, b) =>
        new Date(
          a.event_time,
        ).getTime() -
        new Date(
          b.event_time,
        ).getTime(),
    );

  const totals =
    new Map<string, number>();

  let startEvent:
    | LoggedEvent
    | null = null;

  for (const event of relevant) {
    if (
      event.state === "START"
    ) {
      startEvent = event;
      continue;
    }

    if (
      event.state === "END" &&
      startEvent
    ) {
      const start =
        new Date(
          startEvent.event_time,
        );

      const end =
        new Date(
          event.event_time,
        );

      const hours = Math.max(
        0,
        (
          end.getTime() -
          start.getTime()
        ) /
          3_600_000,
      );

      const key =
        dateKey(
          startEvent.event_time,
        );

      totals.set(
        key,
        (totals.get(key) ?? 0) +
          hours,
      );

      startEvent = null;
    }
  }

  return totals;
}

function buildSleepData(
  events: LoggedEvent[],
  startTime: string,
  endTime: string,
): SleepPoint[] {
  const naps =
    calculateDailySleep(
      events,
      "SLEEP",
    );

  const nighttime =
    calculateDailySleep(
      events,
      "SLEEP_NIGHT",
    );

  return getDatesInRange(
    startTime,
    endTime,
  ).map((date) => ({
    date: displayDate(date),

    naps: Number(
      (
        naps.get(date) ?? 0
      ).toFixed(2),
    ),

    nighttime: Number(
      (
        nighttime.get(date) ??
        0
      ).toFixed(2),
    ),
  }));
}

function buildAverageNapData(
  events: LoggedEvent[],
  startTime: string,
  endTime: string,
): NapPoint[] {
  const sessions =
    new Map<
      string,
      number[]
    >();

  const relevant = [
    ...events,
  ]
    .filter(
      (event) =>
        event.event_type_code ===
          "SLEEP" &&
        event.state,
    )
    .sort(
      (a, b) =>
        new Date(
          a.event_time,
        ).getTime() -
        new Date(
          b.event_time,
        ).getTime(),
    );

  let start:
    | LoggedEvent
    | null = null;

  for (const event of relevant) {
    if (
      event.state === "START"
    ) {
      start = event;
      continue;
    }

    if (
      event.state === "END" &&
      start
    ) {
      const minutes =
        (
          new Date(
            event.event_time,
          ).getTime() -
          new Date(
            start.event_time,
          ).getTime()
        ) /
        60_000;

      const key =
        dateKey(
          start.event_time,
        );

      const values =
        sessions.get(key) ?? [];

      values.push(
        Math.max(
          0,
          minutes,
        ),
      );

      sessions.set(
        key,
        values,
      );

      start = null;
    }
  }

  return getDatesInRange(
    startTime,
    endTime,
  ).map((date) => {
    const values =
      sessions.get(date) ?? [];

    const average =
      values.length
        ? values.reduce(
            (sum, value) =>
              sum + value,
            0,
          ) /
          values.length
        : 0;

    return {
      date: displayDate(date),
      averageNap:
        Math.round(average),
    };
  });
}

function getTimePeriod(
  hour: number,
): string {
  if (
    hour >= 5 &&
    hour < 12
  ) {
    return "Morning";
  }

  if (
    hour >= 12 &&
    hour < 17
  ) {
    return "Afternoon";
  }

  if (
    hour >= 17 &&
    hour < 21
  ) {
    return "Evening";
  }

  return "Night";
}

function buildTimeOfDayData(
  events: LoggedEvent[],
): TimeOfDayPoint[] {
  const order = [
    "Morning",
    "Afternoon",
    "Evening",
    "Night",
  ];

  const counts =
    new Map<string, number>(
      order.map(
        (period) => [
          period,
          0,
        ],
      ),
    );

  for (const event of events) {
    const hour =
      new Date(
        event.event_time,
      ).getHours();

    const period =
      getTimePeriod(hour);

    counts.set(
      period,
      (counts.get(period) ?? 0) +
        1,
    );
  }

  return order.map(
    (period) => ({
      period,
      events:
        counts.get(period) ?? 0,
    }),
  );
}

function buildWalkDistance(
  events: LoggedEvent[],
  startTime: string,
  endTime: string,
): WalkPoint[] {
  const totals =
    new Map<string, number>();

  for (const event of events) {
    if (
      event.event_type_code !==
        "WALK" ||
      !event.numeric_value
    ) {
      continue;
    }

    const value =
      Number(
        event.numeric_value,
      );

    const miles =
      event.unit ===
      "kilometers"
        ? value * 0.621371
        : value;

    const key =
      dateKey(
        event.event_time,
      );

    totals.set(
      key,
      (totals.get(key) ?? 0) +
        miles,
    );
  }

  return getDatesInRange(
    startTime,
    endTime,
  ).map((date) => ({
    date: displayDate(date),

    miles: Number(
      (
        totals.get(date) ?? 0
      ).toFixed(2),
    ),
  }));
}

function buildBehaviorBreakdown(
  events: LoggedEvent[],
): BreakdownPoint[] {
  const counts =
    new Map<string, number>();

  for (const event of events) {
    if (
      event.event_type_code !==
      "BEHAVIOR"
    ) {
      continue;
    }

    const name =
      event.option_name ||
      "Unspecified";

    counts.set(
      name,
      (counts.get(name) ?? 0) +
        1,
    );
  }

  return [
    ...counts.entries(),
  ]
    .map(
      ([name, count]) => ({
        name,
        count,
      }),
    )
    .sort(
      (a, b) =>
        b.count - a.count,
    );
}

function buildSymptomSeverity(
  events: LoggedEvent[],
): SymptomPoint[] {
  return events
    .filter(
      (event) =>
        event.event_type_code ===
          "SYMPTOM" &&
        event.severity !== null &&
        event.severity !==
          undefined,
    )
    .sort(
      (a, b) =>
        new Date(
          a.event_time,
        ).getTime() -
        new Date(
          b.event_time,
        ).getTime(),
    )
    .map((event) => ({
      date: new Date(
        event.event_time,
      ).toLocaleDateString(
        "en-US",
        {
          month: "short",
          day: "numeric",
        },
      ),

      severity:
        Number(
          event.severity,
        ),
    }));
}

function EmptyChart({
  text,
}: {
  text: string;
}) {
  return (
    <div className="chart-empty">
      <span>🐾</span>
      <p>{text}</p>
    </div>
  );
}

export function InsightsCharts({
  events,
  startTime,
  endTime,
  chartPreferences,
}: Props) {
  const enabled =
    [...chartPreferences]
      .filter(
        (chart) =>
          chart.is_enabled,
      )
      .sort(
        (a, b) =>
          a.display_order -
          b.display_order,
      );

  const dailyActivity =
    buildDailyActivity(
      events,
      startTime,
      endTime,
    );

  const pottyOutcomes =
    buildPottyOutcomes(
      events,
    );

  const pottyByHour =
    buildPottyByHour(
      events,
    );

  const accidentTrend =
    buildAccidentTrend(
      events,
      startTime,
      endTime,
    );

  const sleepData =
    buildSleepData(
      events,
      startTime,
      endTime,
    );

  const napData =
    buildAverageNapData(
      events,
      startTime,
      endTime,
    );

  const timeOfDay =
    buildTimeOfDayData(
      events,
    );

  const walkData =
    buildWalkDistance(
      events,
      startTime,
      endTime,
    );

  const behaviorData =
    buildBehaviorBreakdown(
      events,
    );

  const symptomData =
    buildSymptomSeverity(
      events,
    );

  function renderChart(
    code: string,
  ) {
    switch (code) {
      case "DAILY_ACTIVITY":
        return (
          <article className="chart-card chart-card-wide">
            <div className="chart-heading">
              <div>
                <h3>
                  Activity by day
                </h3>
                <p>
                  Total logged events
                  across the selected
                  period.
                </p>
              </div>
            </div>

            <div className="chart-container">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <LineChart
                  data={
                    dailyActivity
                  }
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                  />

                  <XAxis
                    dataKey="date"
                  />

                  <YAxis
                    allowDecimals={
                      false
                    }
                  />

                  <Tooltip />

                  <Line
                    type="monotone"
                    dataKey="events"
                    name="Events"
                    stroke="var(--paw-accent)"
                    strokeWidth={3}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </article>
        );

      case "POTTY_OUTCOMES":
        return (
          <article className="chart-card">
            <div className="chart-heading">
              <div>
                <h3>
                  Potty outcomes
                </h3>
                <p>
                  Where potty events
                  happened.
                </p>
              </div>
            </div>

            {pottyOutcomes.length ? (
              <div className="chart-container">
                <ResponsiveContainer
                  width="100%"
                  height="100%"
                >
                  <BarChart
                    data={
                      pottyOutcomes
                    }
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      vertical={
                        false
                      }
                    />

                    <XAxis
                      dataKey="outcome"
                    />

                    <YAxis
                      allowDecimals={
                        false
                      }
                    />

                    <Tooltip />

                    <Bar
                      dataKey="count"
                      fill="var(--paw-accent)"
                      radius={[
                        8,
                        8,
                        0,
                        0,
                      ]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyChart text="No potty data in this period." />
            )}
          </article>
        );

      case "POTTY_BY_HOUR":
        return (
          <article className="chart-card chart-card-wide">
            <div className="chart-heading">
              <div>
                <h3>
                  Potty activity by hour
                </h3>
                <p>
                  See when pee and poop
                  events most often occur.
                </p>
              </div>
            </div>

            <div className="chart-container chart-container-large">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <BarChart
                  data={
                    pottyByHour
                  }
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                  />

                  <XAxis
                    dataKey="hour"
                    interval={2}
                  />

                  <YAxis
                    allowDecimals={
                      false
                    }
                  />

                  <Tooltip />
                  <Legend />

                  <Bar
                    dataKey="pee"
                    name="Pee"
                    fill="var(--paw-accent)"
                    radius={[
                      6,
                      6,
                      0,
                      0,
                    ]}
                  />

                  <Bar
                    dataKey="poop"
                    name="Poop"
                    fill="var(--paw-accent)"
                    fillOpacity={
                      0.45
                    }
                    radius={[
                      6,
                      6,
                      0,
                      0,
                    ]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </article>
        );

      case "ACCIDENT_TREND":
        return (
          <article className="chart-card chart-card-wide">
            <div className="chart-heading">
              <div>
                <h3>
                  Accident trend
                </h3>
                <p>
                  Potty accidents by
                  day.
                </p>
              </div>
            </div>

            <div className="chart-container">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <LineChart
                  data={
                    accidentTrend
                  }
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                  />

                  <XAxis
                    dataKey="date"
                  />

                  <YAxis
                    allowDecimals={
                      false
                    }
                  />

                  <Tooltip />

                  <Line
                    type="monotone"
                    dataKey="accidents"
                    name="Accidents"
                    stroke="var(--paw-accent)"
                    strokeWidth={3}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </article>
        );

      case "SLEEP_DURATION":
        return (
          <article className="chart-card chart-card-wide">
            <div className="chart-heading">
              <div>
                <h3>
                  Sleep duration
                </h3>
                <p>
                  Nap and nighttime
                  sleep by day.
                </p>
              </div>
            </div>

            <div className="chart-container chart-container-large">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <BarChart
                  data={
                    sleepData
                  }
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                  />

                  <XAxis
                    dataKey="date"
                  />

                  <YAxis unit="h" />

                  <Tooltip />
                  <Legend />

                  <Bar
                    dataKey="naps"
                    name="Naps"
                    fill="var(--paw-accent)"
                  />

                  <Bar
                    dataKey="nighttime"
                    name="Night sleep"
                    fill="var(--paw-accent)"
                    fillOpacity={
                      0.45
                    }
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </article>
        );

      case "AVG_NAP_DURATION":
        return (
          <article className="chart-card chart-card-wide">
            <div className="chart-heading">
              <div>
                <h3>
                  Average nap duration
                </h3>
                <p>
                  Average completed nap
                  length by day.
                </p>
              </div>
            </div>

            <div className="chart-container">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <LineChart
                  data={napData}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                  />

                  <XAxis
                    dataKey="date"
                  />

                  <YAxis
                    unit="m"
                  />

                  <Tooltip />

                  <Line
                    type="monotone"
                    dataKey="averageNap"
                    name="Average nap"
                    stroke="var(--paw-accent)"
                    strokeWidth={3}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </article>
        );

      case "ACTIVITY_BY_TIME":
        return (
          <article className="chart-card">
            <div className="chart-heading">
              <div>
                <h3>
                  Activity by time
                </h3>
                <p>
                  Morning, afternoon,
                  evening, and night.
                </p>
              </div>
            </div>

            <div className="chart-container">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <BarChart
                  data={
                    timeOfDay
                  }
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                  />

                  <XAxis
                    dataKey="period"
                  />

                  <YAxis
                    allowDecimals={
                      false
                    }
                  />

                  <Tooltip />

                  <Bar
                    dataKey="events"
                    name="Events"
                    fill="var(--paw-accent)"
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </article>
        );

      case "WALK_DISTANCE":
        return (
          <article className="chart-card chart-card-wide">
            <div className="chart-heading">
              <div>
                <h3>
                  Walk distance
                </h3>
                <p>
                  Logged walking distance
                  by day.
                </p>
              </div>
            </div>

            <div className="chart-container">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <LineChart
                  data={walkData}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                  />

                  <XAxis
                    dataKey="date"
                  />

                  <YAxis unit=" mi" />

                  <Tooltip />

                  <Line
                    type="monotone"
                    dataKey="miles"
                    name="Miles"
                    stroke="var(--paw-accent)"
                    strokeWidth={3}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </article>
        );

      case "BEHAVIOR_BREAKDOWN":
        return (
          <article className="chart-card">
            <div className="chart-heading">
              <div>
                <h3>
                  Behavior breakdown
                </h3>
                <p>
                  Most frequently logged
                  behaviors.
                </p>
              </div>
            </div>

            {behaviorData.length ? (
              <div className="chart-container">
                <ResponsiveContainer
                  width="100%"
                  height="100%"
                >
                  <BarChart
                    data={
                      behaviorData
                    }
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      vertical={
                        false
                      }
                    />

                    <XAxis
                      dataKey="name"
                    />

                    <YAxis
                      allowDecimals={
                        false
                      }
                    />

                    <Tooltip />

                    <Bar
                      dataKey="count"
                      name="Logs"
                      fill="var(--paw-accent)"
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyChart text="No behavior logs in this period." />
            )}
          </article>
        );

      case "SYMPTOM_SEVERITY":
        return (
          <article className="chart-card chart-card-wide">
            <div className="chart-heading">
              <div>
                <h3>
                  Symptom severity
                </h3>
                <p>
                  Severity of logged
                  symptoms over time.
                </p>
              </div>
            </div>

            {symptomData.length ? (
              <div className="chart-container">
                <ResponsiveContainer
                  width="100%"
                  height="100%"
                >
                  <LineChart
                    data={
                      symptomData
                    }
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      vertical={
                        false
                      }
                    />

                    <XAxis
                      dataKey="date"
                    />

                    <YAxis
                      domain={[
                        0,
                        10,
                      ]}
                    />

                    <Tooltip />

                    <Line
                      type="monotone"
                      dataKey="severity"
                      name="Severity"
                      stroke="var(--paw-accent)"
                      strokeWidth={3}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyChart text="No symptom severity data in this period." />
            )}
          </article>
        );

      default:
        return null;
    }
  }

  if (
    enabled.length === 0
  ) {
    return (
      <section className="insights-charts-section">
        <div className="empty-card">
          <p>
            No insight charts are enabled.
          </p>

          <p>
            Choose charts in Settings.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="insights-charts-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">
            Patterns
          </p>

          <h2>
            Activity trends
          </h2>
        </div>
      </div>

      <div className="insights-chart-grid">
        {enabled.map(
          (chart) => (
            <div
              key={
                chart.code
              }
              className="chart-slot"
            >
              {renderChart(
                chart.code,
              )}
            </div>
          ),
        )}
      </div>
    </section>
  );
}