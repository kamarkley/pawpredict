import { useEffect, useState, type CSSProperties } from "react";

import { getPottyPrediction } from "../services/api";
import type { PottyPrediction } from "../types/prediction";

interface Props {
  dogId: string;
  dogName: string;
  refreshKey: number;
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function minutesLabel(value: number | null): string {
  if (value === null) return "No prior log";
  const rounded = Math.max(0, Math.round(value));
  if (rounded < 60) return `${rounded} min`;
  const hours = Math.floor(rounded / 60);
  const minutes = rounded % 60;
  return minutes ? `${hours}h ${minutes}m` : `${hours}h`;
}

function riskLabel(probability: number): string {
  if (probability >= 0.65) return "High";
  if (probability >= 0.4) return "Rising";
  return "Lower";
}

function modeLabel(prediction: PottyPrediction): string {
  return prediction.mode === "TRAINED_MODEL" ? "Personalized ML model" : "Learning mode";
}

export function PottyPredictionCard({ dogId, dogName, refreshKey }: Props) {
  const [prediction, setPrediction] = useState<PottyPrediction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setError(null);
    try {
      setPrediction(await getPottyPrediction(dogId));
    } catch (err) {
      if (err instanceof Error) setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();

    getPottyPrediction(dogId, controller.signal)
      .then((result) => {
        setPrediction(result);
        setError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    const interval = window.setInterval(() => {
      getPottyPrediction(dogId)
        .then((result) => {
          setPrediction(result);
          setError(null);
        })
        .catch((err: unknown) => {
          if (err instanceof Error) setError(err.message);
        });
    }, 5 * 60_000);

    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, [dogId, refreshKey]);

  if (loading && !prediction) {
    return (
      <section className="prediction-card prediction-card-loading">
        <div className="prediction-skeleton" />
        <div><p className="eyebrow">PawPredict AI</p><h2>Calculating potty risk…</h2></div>
      </section>
    );
  }

  if (error && !prediction) {
    return (
      <section className="prediction-card">
        <div className="prediction-heading-row">
          <div><p className="eyebrow">PawPredict AI</p><h2>Potty prediction</h2></div>
          <button className="icon-button" type="button" onClick={() => void refresh()} aria-label="Retry prediction">↻</button>
        </div>
        <p className="event-error">{error}</p>
      </section>
    );
  }

  if (!prediction) return null;

  const risk = Math.round(prediction.probability_any * 100);
  const ringStyle = { "--risk": `${risk}%` } as CSSProperties & Record<"--risk", string>;

  return (
    <section className="prediction-card">
      <div className="prediction-heading-row">
        <div>
          <p className="eyebrow">PawPredict AI</p>
          <h2>Next 10 minutes</h2>
          <p className="prediction-subcopy">A personalized estimate using {dogName}&apos;s own tracking history.</p>
        </div>
        <button className="icon-button" type="button" onClick={() => void refresh()} aria-label="Refresh prediction">↻</button>
      </div>

      <div className="prediction-main-grid">
        <div className="risk-ring" style={ringStyle}>
          <div className="risk-ring-inner">
            <strong>{prediction.currently_sleeping ? "—" : `${risk}%`}</strong>
            <span>{prediction.currently_sleeping ? "Paused" : `${riskLabel(prediction.probability_any)} chance`}</span>
          </div>
        </div>

        <div className="prediction-summary">
          <div className="prediction-badges">
            <span className={`model-badge ${prediction.mode === "TRAINED_MODEL" ? "trained" : "early"}`}>
              {modeLabel(prediction)}
            </span>
            <span className={`confidence-badge confidence-${prediction.confidence.toLowerCase()}`}>
              {prediction.confidence.toLowerCase()} confidence
            </span>
          </div>
          <h3>{prediction.recommendation}</h3>
          <div className="prediction-split">
            <div><span>Pee</span><strong>{percent(prediction.probability_pee)}</strong></div>
            <div><span>Poop</span><strong>{percent(prediction.probability_poop)}</strong></div>
          </div>
        </div>
      </div>

      {prediction.mode === "EARLY_ESTIMATE" && (
        <div className="prediction-context-note learning-mode-note">
          <span>🧠</span>
          <p><strong>Learning mode.</strong> PawPredict is building this dog&apos;s personal baseline from {prediction.exact_potty_events} exact potty logs across {prediction.data_days} days. The fitted personalized model unlocks automatically when there is enough clean history.</p>
        </div>
      )}

      {(prediction.currently_sleeping || prediction.currently_unobserved) && (
        <div className="prediction-context-note">
          <span>{prediction.currently_sleeping ? "😴" : "◌"}</span>
          <p>{prediction.currently_sleeping ? "Sleep is currently logged, so the take-out cue is intentionally paused." : "You are currently in an unobserved period, so this estimate has less immediate context."}</p>
        </div>
      )}

      <div className="prediction-timing-grid">
        <div><span>Since pee</span><strong>{minutesLabel(prediction.minutes_since_pee)}</strong></div>
        <div><span>Since poop</span><strong>{minutesLabel(prediction.minutes_since_poop)}</strong></div>
        <div><span>Since wake</span><strong>{minutesLabel(prediction.minutes_since_wake)}</strong></div>
      </div>

      <div className="forecast-block">
        <div className="compact-heading"><strong>Next hour</strong><span>assuming no new events</span></div>
        <div className="forecast-bars" aria-label="Potty risk forecast for the next hour">
          {prediction.forecast.map((point) => (
            <div className="forecast-point" key={point.minutes_ahead} title={`${point.minutes_ahead} min: ${percent(point.probability)}`}>
              <div className="forecast-track"><i style={{ height: `${Math.max(5, point.probability * 100)}%` }} /></div>
              <span>{point.minutes_ahead === 0 ? "now" : `+${point.minutes_ahead}`}</span>
            </div>
          ))}
        </div>
      </div>

      {prediction.drivers.length > 0 && (
        <div className="prediction-drivers">
          <div className="compact-heading"><strong>What is influencing this</strong><span>{prediction.data_days} days of data</span></div>
          <div className="driver-list">
            {prediction.drivers.map((driver) => (
              <div className="driver-row" key={`${driver.label}-${driver.detail}`}>
                <span className={`driver-arrow driver-${driver.direction.toLowerCase()}`}>
                  {driver.direction === "UP" ? "↑" : driver.direction === "DOWN" ? "↓" : "•"}
                </span>
                <div><strong>{driver.label}</strong><small>{driver.detail}</small></div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="prediction-footer">
        <span>{prediction.training_examples.toLocaleString()} usable training snapshots</span>
        <span>{prediction.exact_potty_events} exact potty logs</span>
        <span>Updated {new Date(prediction.generated_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span>
      </div>
    </section>
  );
}
