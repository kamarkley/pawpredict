import { useEffect, useMemo, useState } from "react";

import {
  getChartPreferences,
  getUIPreferences,
  updateChartPreferences,
  updateUIPreferences,
} from "../services/api";

import type {
  ChartPreference,
  UIPreference,
} from "../types/dashboard";

interface Props {
  dogId: string;
  onPreferencesChanged?: () => void;
}

const COLOR_OPTIONS = [
  {
    name: "Lavender",
    value: "#6D63D9",
  },
  {
    name: "Blue",
    value: "#4F7EDB",
  },
  {
    name: "Sage",
    value: "#6F9E7A",
  },
  {
    name: "Pink",
    value: "#D879A6",
  },
  {
    name: "Peach",
    value: "#D98A67",
  },
  {
    name: "Teal",
    value: "#4D9B98",
  },
  {
    name: "Purple",
    value: "#8A63D2",
  },
  {
    name: "Coral",
    value: "#D96F6F",
  },
];

function sortPreferences(
  preferences: ChartPreference[],
): ChartPreference[] {
  return [...preferences].sort(
    (a, b) => a.display_order - b.display_order,
  );
}

export function DashboardCustomization({
  dogId,
  onPreferencesChanged,
}: Props) {
  const [charts, setCharts] = useState<
    ChartPreference[]
  >([]);

  const [uiPreference, setUIPreference] =
    useState<UIPreference | null>(null);

  const [customColor, setCustomColor] =
    useState("#6D63D9");

  const [loading, setLoading] =
    useState(true);

  const [savingCharts, setSavingCharts] =
    useState(false);

  const [savingColor, setSavingColor] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const [message, setMessage] =
    useState<string | null>(null);

  useEffect(() => {
    const controller =
      new AbortController();

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const [
          chartResults,
          uiResults,
        ] = await Promise.all([
          getChartPreferences(
            dogId,
            controller.signal,
          ),
          getUIPreferences(
            dogId,
            controller.signal,
          ),
        ]);

        setCharts(
          sortPreferences(chartResults),
        );

        setUIPreference(uiResults);

        setCustomColor(
          uiResults.accent_color,
        );
      } catch (err) {
        if (
          err instanceof Error &&
          err.name !== "AbortError"
        ) {
          setError(err.message);
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
  }, [dogId]);

  const selectedColor =
    uiPreference?.accent_color ??
    "#6D63D9";

  const selectedPresetName =
    useMemo(() => {
      return COLOR_OPTIONS.find(
        (option) =>
          option.value.toUpperCase() ===
          selectedColor.toUpperCase(),
      )?.name;
    }, [selectedColor]);

  function setChartEnabled(
    code: string,
    enabled: boolean,
  ) {
    setCharts((current) =>
      current.map((chart) =>
        chart.code === code
          ? {
              ...chart,
              is_enabled: enabled,
            }
          : chart,
      ),
    );
  }

  function moveChart(
    code: string,
    direction: "UP" | "DOWN",
  ) {
    setCharts((current) => {
      const ordered =
        sortPreferences(current);

      const index =
        ordered.findIndex(
          (chart) =>
            chart.code === code,
        );

      if (index === -1) {
        return current;
      }

      const targetIndex =
        direction === "UP"
          ? index - 1
          : index + 1;

      if (
        targetIndex < 0 ||
        targetIndex >= ordered.length
      ) {
        return current;
      }

      const next = [...ordered];

      const currentChart =
        next[index];

      next[index] =
        next[targetIndex];

      next[targetIndex] =
        currentChart;

      return next.map(
        (chart, chartIndex) => ({
          ...chart,
          display_order:
            chartIndex + 1,
        }),
      );
    });
  }

  async function saveCharts() {
    setSavingCharts(true);
    setError(null);
    setMessage(null);

    try {
      const result =
        await updateChartPreferences(
          dogId,
          sortPreferences(charts).map(
            (
              chart,
              index,
            ) => ({
              code: chart.code,
              is_enabled:
                chart.is_enabled,
              display_order:
                index + 1,
            }),
          ),
        );

      setCharts(
        sortPreferences(result),
      );

      setMessage(
        "Chart preferences saved.",
      );

      onPreferencesChanged?.();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not save chart preferences.",
      );
    } finally {
      setSavingCharts(false);
    }
  }

  async function saveColor(
    color: string,
  ) {
    setSavingColor(true);
    setError(null);
    setMessage(null);

    try {
      const result =
        await updateUIPreferences(
          dogId,
          color,
        );

      setUIPreference(result);

      setCustomColor(
        result.accent_color,
      );

      document.documentElement.style.setProperty(
        "--paw-accent",
        result.accent_color,
      );

      setMessage(
        "Theme color updated.",
      );

      onPreferencesChanged?.();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not update theme color.",
      );
    } finally {
      setSavingColor(false);
    }
  }

  if (loading) {
    return (
      <section className="settings-card">
        <p className="status-message">
          Loading dashboard settings…
        </p>
      </section>
    );
  }

  return (
    <section className="dashboard-customization">
      <div className="settings-card">
        <div className="settings-section-heading">
          <div>
            <p className="eyebrow">
              Appearance
            </p>

            <h2>
              PawPredict color
            </h2>

            <p>
              Choose one accent color
              for buttons, controls,
              and charts.
            </p>
          </div>
        </div>

        {message && (
          <p className="success-message">
            {message}
          </p>
        )}

        {error && (
          <p className="event-error">
            {error}
          </p>
        )}

        <div className="color-option-grid">
          {COLOR_OPTIONS.map(
            (option) => {
              const selected =
                selectedColor.toUpperCase() ===
                option.value.toUpperCase();

              return (
                <button
                  key={
                    option.value
                  }
                  className={
                    selected
                      ? "color-option selected"
                      : "color-option"
                  }
                  type="button"
                  disabled={
                    savingColor
                  }
                  onClick={() =>
                    void saveColor(
                      option.value,
                    )
                  }
                >
                  <span
                    className="color-swatch"
                    style={{
                      background:
                        option.value,
                    }}
                    aria-hidden="true"
                  />

                  <span>
                    {option.name}
                  </span>

                  {selected && (
                    <small>
                      Selected
                    </small>
                  )}
                </button>
              );
            },
          )}
        </div>

        <div className="custom-color-row">
          <label className="field-label">
            Custom color

            <div className="custom-color-control">
              <input
                type="color"
                value={
                  customColor
                }
                disabled={
                  savingColor
                }
                onChange={(
                  event,
                ) =>
                  setCustomColor(
                    event.target
                      .value,
                  )
                }
              />

              <input
                type="text"
                value={
                  customColor
                }
                maxLength={7}
                disabled={
                  savingColor
                }
                onChange={(
                  event,
                ) =>
                  setCustomColor(
                    event.target
                      .value,
                  )
                }
              />

              <button
                className="save-button"
                type="button"
                disabled={
                  savingColor ||
                  !/^#[0-9A-Fa-f]{6}$/.test(
                    customColor,
                  )
                }
                onClick={() =>
                  void saveColor(
                    customColor,
                  )
                }
              >
                {savingColor
                  ? "Saving…"
                  : "Apply"}
              </button>
            </div>
          </label>

          <p className="settings-helper">
            {selectedPresetName
              ? `Current theme: ${selectedPresetName}`
              : `Current theme: ${selectedColor}`}
          </p>
        </div>
      </div>

      <div className="settings-card">
        <div className="settings-section-heading">
          <div>
            <p className="eyebrow">
              Insights
            </p>

            <h2>
              Insight charts
            </h2>

            <p>
              Choose which graphs
              appear and the order
              they are shown.
            </p>
          </div>
        </div>

        <div className="chart-preference-list">
          {sortPreferences(
            charts,
          ).map(
            (
              chart,
              index,
            ) => (
              <article
                className="chart-preference-row"
                key={
                  chart.code
                }
              >
                <label className="chart-toggle">
                  <input
                    type="checkbox"
                    checked={
                      chart.is_enabled
                    }
                    onChange={(
                      event,
                    ) =>
                      setChartEnabled(
                        chart.code,
                        event.target
                          .checked,
                      )
                    }
                  />

                  <span>
                    <strong>
                      {
                        chart.display_name
                      }
                    </strong>

                    {chart.description && (
                      <small>
                        {
                          chart.description
                        }
                      </small>
                    )}
                  </span>
                </label>

                <div className="chart-order-controls">
                  <button
                    type="button"
                    aria-label={`Move ${chart.display_name} up`}
                    disabled={
                      index === 0
                    }
                    onClick={() =>
                      moveChart(
                        chart.code,
                        "UP",
                      )
                    }
                  >
                    ↑
                  </button>

                  <button
                    type="button"
                    aria-label={`Move ${chart.display_name} down`}
                    disabled={
                      index ===
                      charts.length -
                        1
                    }
                    onClick={() =>
                      moveChart(
                        chart.code,
                        "DOWN",
                      )
                    }
                  >
                    ↓
                  </button>
                </div>
              </article>
            ),
          )}
        </div>

        <div className="form-actions">
          <button
            className="save-button"
            type="button"
            disabled={
              savingCharts
            }
            onClick={() =>
              void saveCharts()
            }
          >
            {savingCharts
              ? "Saving…"
              : "Save chart settings"}
          </button>
        </div>
      </div>
    </section>
  );
}