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

import type { LoggedEvent } from "../types/event";

interface Props {
  events: LoggedEvent[];
  startTime: string;
  endTime: string;
}

interface DailyActivityPoint {
  date: string;
  events: number;
}

interface PottyPoint {
  outcome: string;
  count: number;
}

interface SleepPoint {
  date: string;
  naps: number;
  nighttime: number;
}

interface TimeOfDayPoint {
  period: string;
  events: number;
}

function dateKey(timestamp: string): string {
  const date = new Date(timestamp);

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function displayDate(dateString: string): string {
  const date = new Date(`${dateString}T00:00:00`);

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function getDatesInRange(
  startTime: string,
  endTime: string,
): string[] {
  const dates: string[] = [];

  const current = new Date(startTime);
  current.setHours(0, 0, 0, 0);

  const end = new Date(endTime);

  while (current < end) {
    const year = current.getFullYear();
    const month = String(
      current.getMonth() + 1,
    ).padStart(2, "0");
    const day = String(
      current.getDate(),
    ).padStart(2, "0");

    dates.push(`${year}-${month}-${day}`);

    current.setDate(current.getDate() + 1);
  }

  return dates;
}

function buildDailyActivity(
  events: LoggedEvent[],
  startTime: string,
  endTime: string,
): DailyActivityPoint[] {
  const counts = new Map<string, number>();

  for (const event of events) {
    const key = dateKey(event.event_time);

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
  const pottyEvents = events.filter(
    (event) =>
      event.event_type_code === "PEE" ||
      event.event_type_code === "POOP",
  );

  const counts = new Map<string, number>();

  for (const event of pottyEvents) {
    const outcome =
      event.option_name?.trim() ||
      "Not specified";

    counts.set(
      outcome,
      (counts.get(outcome) ?? 0) + 1,
    );
  }

  return [...counts.entries()]
    .map(([outcome, count]) => ({
      outcome,
      count,
    }))
    .sort((a, b) => b.count - a.count);
}

function calculateDailySleep(
  events: LoggedEvent[],
  code: string,
): Map<string, number> {
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

  const totals = new Map<string, number>();

  let startEvent: LoggedEvent | null = null;

  for (const event of relevant) {
    if (event.state === "START") {
      startEvent = event;
      continue;
    }

    if (
      event.state === "END" &&
      startEvent
    ) {
      const start = new Date(
        startEvent.event_time,
      );

      const end = new Date(
        event.event_time,
      );

      const hours = Math.max(
        0,
        (end.getTime() -
          start.getTime()) /
          3_600_000,
      );

      const key = dateKey(
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
  const napTotals =
    calculateDailySleep(
      events,
      "SLEEP",
    );

  const nighttimeTotals =
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
      (napTotals.get(date) ?? 0).toFixed(2),
    ),
    nighttime: Number(
      (
        nighttimeTotals.get(date) ?? 0
      ).toFixed(2),
    ),
  }));
}

function getTimePeriod(
  hour: number,
): string {
  if (hour >= 5 && hour < 12) {
    return "Morning";
  }

  if (hour >= 12 && hour < 17) {
    return "Afternoon";
  }

  if (hour >= 17 && hour < 21) {
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

  const counts = new Map<
    string,
    number
  >(
    order.map((period) => [
      period,
      0,
    ]),
  );

  for (const event of events) {
    const hour = new Date(
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

  return order.map((period) => ({
    period,
    events:
      counts.get(period) ?? 0,
  }));
}

function hasMultipleDays(
  startTime: string,
  endTime: string,
): boolean {
  const duration =
    new Date(endTime).getTime() -
    new Date(startTime).getTime();

  return duration >
    86_400_000;
}

export function InsightsCharts({
  events,
  startTime,
  endTime,
}: Props) {
  const dailyActivity =
    buildDailyActivity(
      events,
      startTime,
      endTime,
    );

  const pottyOutcomes =
    buildPottyOutcomes(events);

  const sleepData =
    buildSleepData(
      events,
      startTime,
      endTime,
    );

  const timeOfDay =
    buildTimeOfDayData(events);

  const showDailyTrend =
    hasMultipleDays(
      startTime,
      endTime,
    );

  const hasPottyData =
    pottyOutcomes.length > 0;

  const hasSleepData =
    sleepData.some(
      (day) =>
        day.naps > 0 ||
        day.nighttime > 0,
    );

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
        {showDailyTrend && (
          <article className="chart-card chart-card-wide">
            <div className="chart-heading">
              <div>
                <h3>
                  Activity by day
                </h3>

                <p>
                  Total logged events across
                  the selected period.
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
                  margin={{
                    top: 10,
                    right: 12,
                    left: -12,
                    bottom: 0,
                  }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                  />

                  <XAxis
                    dataKey="date"
                    tickLine={false}
                    axisLine={false}
                  />

                  <YAxis
                    allowDecimals={false}
                    tickLine={false}
                    axisLine={false}
                  />

                  <Tooltip />

                  <Line
                    type="monotone"
                    dataKey="events"
                    name="Events"
                    stroke="currentColor"
                    strokeWidth={3}
                    dot
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </article>
        )}

        <article className="chart-card">
          <div className="chart-heading">
            <div>
              <h3>
                Potty outcomes
              </h3>

              <p>
                Where potty events happened.
              </p>
            </div>
          </div>

          {hasPottyData ? (
            <div className="chart-container">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <BarChart
                  data={
                    pottyOutcomes
                  }
                  margin={{
                    top: 10,
                    right: 12,
                    left: -12,
                    bottom: 0,
                  }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                  />

                  <XAxis
                    dataKey="outcome"
                    tickLine={false}
                    axisLine={false}
                  />

                  <YAxis
                    allowDecimals={false}
                    tickLine={false}
                    axisLine={false}
                  />

                  <Tooltip />

                  <Bar
                    dataKey="count"
                    name="Potty events"
                    fill="currentColor"
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
            <div className="chart-empty">
              <span>🐾</span>
              <p>
                No potty data in this period.
              </p>
            </div>
          )}
        </article>

        <article className="chart-card">
          <div className="chart-heading">
            <div>
              <h3>
                Activity by time
              </h3>

              <p>
                When most activity is logged.
              </p>
            </div>
          </div>

          <div className="chart-container">
            <ResponsiveContainer
              width="100%"
              height="100%"
            >
              <BarChart
                data={timeOfDay}
                margin={{
                  top: 10,
                  right: 12,
                  left: -12,
                  bottom: 0,
                }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                />

                <XAxis
                  dataKey="period"
                  tickLine={false}
                  axisLine={false}
                />

                <YAxis
                  allowDecimals={false}
                  tickLine={false}
                  axisLine={false}
                />

                <Tooltip />

                <Bar
                  dataKey="events"
                  name="Events"
                  fill="currentColor"
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
        </article>

        {hasSleepData && (
          <article className="chart-card chart-card-wide">
            <div className="chart-heading">
              <div>
                <h3>
                  Sleep duration
                </h3>

                <p>
                  Completed nap and nighttime
                  sleep sessions by day.
                </p>
              </div>
            </div>

            <div className="chart-container chart-container-large">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <BarChart
                  data={sleepData}
                  margin={{
                    top: 10,
                    right: 12,
                    left: -4,
                    bottom: 0,
                  }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                  />

                  <XAxis
                    dataKey="date"
                    tickLine={false}
                    axisLine={false}
                  />

                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    unit="h"
                  />

                  <Tooltip />

                  <Legend />

                  <Bar
                    dataKey="naps"
                    name="Naps"
                    fill="currentColor"
                    radius={[
                      6,
                      6,
                      0,
                      0,
                    ]}
                  />

                  <Bar
                    dataKey="nighttime"
                    name="Night sleep"
                    fill="currentColor"
                    fillOpacity={0.45}
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
        )}
      </div>
    </section>
  );
}