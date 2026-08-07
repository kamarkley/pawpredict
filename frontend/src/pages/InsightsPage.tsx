import { useMemo, useState } from "react";

import { DailyStatsDashboard } from "../components/DailyStatsDashboard";
import {
  getInsightDateRange,
  getPreviousInsightDateRange,
  type InsightRangePreset,
} from "../utils/date";

interface Props {
  dogId: string;
  dogBirthDate: string;
  refreshKey: number;
  preferenceRefreshKey: number;
}

function getTodayInputValue(): string {
  const now = new Date();
  const localDate = new Date(
    now.getTime() - now.getTimezoneOffset() * 60_000,
  );

  return localDate.toISOString().slice(0, 10);
}

export function InsightsPage({
  dogId,
  dogBirthDate,
  refreshKey,
  preferenceRefreshKey,
}: Props) {
  const [preset, setPreset] =
    useState<InsightRangePreset>("TODAY");

  const today = getTodayInputValue();

  const [customStart, setCustomStart] = useState(today);
  const [customEnd, setCustomEnd] = useState(today);

  const range = useMemo(
    () =>
      getInsightDateRange(
        preset,
        dogBirthDate,
        customStart,
        customEnd,
      ),
    [preset, dogBirthDate, customStart, customEnd],
  );

  const comparisonRange = useMemo(
    () => getPreviousInsightDateRange(preset, range),
    [preset, range],
  );

  const customRangeInvalid =
    preset === "CUSTOM" &&
    Boolean(customStart) &&
    Boolean(customEnd) &&
    customStart > customEnd;

  return (
    <section>
      <div className="insight-range-card">
        <div className="insight-range-heading">
          <div>
            <p className="eyebrow">Time period</p>
            <h2>Choose an insight range</h2>
          </div>
        </div>

        <div
          className="range-preset-row"
          role="group"
          aria-label="Insight date range"
        >
          <button
            className={preset === "TODAY" ? "active" : ""}
            type="button"
            onClick={() => setPreset("TODAY")}
          >
            Today
          </button>

          <button
            className={
              preset === "LAST_7_DAYS" ? "active" : ""
            }
            type="button"
            onClick={() => setPreset("LAST_7_DAYS")}
          >
            7 days
          </button>

          <button
            className={
              preset === "LAST_30_DAYS" ? "active" : ""
            }
            type="button"
            onClick={() => setPreset("LAST_30_DAYS")}
          >
            30 days
          </button>

          <button
            className={preset === "ALL_TIME" ? "active" : ""}
            type="button"
            onClick={() => setPreset("ALL_TIME")}
          >
            All time
          </button>

          <button
            className={preset === "CUSTOM" ? "active" : ""}
            type="button"
            onClick={() => setPreset("CUSTOM")}
          >
            Custom
          </button>
        </div>

        {preset === "CUSTOM" && (
          <div className="custom-range-fields">
            <label className="field-label">
              Start date
              <input
                type="date"
                value={customStart}
                max={today}
                onChange={(event) =>
                  setCustomStart(event.target.value)
                }
              />
            </label>

            <label className="field-label">
              End date
              <input
                type="date"
                value={customEnd}
                max={today}
                onChange={(event) =>
                  setCustomEnd(event.target.value)
                }
              />
            </label>
          </div>
        )}

        {customRangeInvalid && (
          <p className="event-error" role="alert">
            The end date must be on or after the start date.
          </p>
        )}
      </div>

      {!customRangeInvalid && (
        <DailyStatsDashboard
          dogId={dogId}
          startTime={range.start}
          endTime={range.end}
          rangeLabel={range.label}
          previousStartTime={comparisonRange?.start ?? null}
          previousEndTime={comparisonRange?.end ?? null}
          comparisonLabel={comparisonRange?.label ?? null}
          refreshKey={refreshKey}
          preferenceRefreshKey={preferenceRefreshKey}
        />
      )}
    </section>
  );
}