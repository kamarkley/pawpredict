import { useEffect, useState } from "react";

import { getPottyModelReport } from "../services/api";
import type { PottyModelReport, TargetModelMetrics } from "../types/prediction";

interface Props {
  dogId: string;
  refreshKey: number;
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function metric(value: number | null): string {
  return value === null ? "—" : value.toFixed(3);
}

function targetLabel(target: TargetModelMetrics["target"]): string {
  if (target === "ANY") return "Any potty";
  if (target === "PEE") return "Pee";
  return "Poop";
}

export function ModelPerformancePanel({ dogId, refreshKey }: Props) {
  const [report, setReport] = useState<PottyModelReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getPottyModelReport(dogId, controller.signal)
      .then(setReport)
      .catch((err: unknown) => {
        if (err instanceof Error && err.name !== "AbortError") setError(err.message);
      });
    return () => controller.abort();
  }, [dogId, refreshKey]);

  return (
    <section className="model-report-card">
      <div className="model-report-heading">
        <div>
          <p className="eyebrow">Machine learning</p>
          <h2>Potty prediction model</h2>
          <p>Real model status and holdout performance for the 10-minute prediction target.</p>
        </div>
        {report && <span className={`confidence-badge confidence-${report.confidence.toLowerCase()}`}>{report.confidence.toLowerCase()}</span>}
      </div>

      {error && <p className="event-error">{error}</p>}
      {!report && !error && <p className="status-message">Evaluating prediction model…</p>}

      {report && (
        <>
          <div className="model-status-banner">
            <strong>{report.mode === "TRAINED_MODEL" ? "Personalized model active" : "Collecting enough clean data for the fitted model"}</strong>
            <span>{report.confidence_label}</span>
          </div>

          <div className="model-data-grid">
            <div><span>Model history</span><strong>{report.data_days} days</strong></div>
            <div><span>Training snapshots</span><strong>{report.usable_training_examples.toLocaleString()}</strong></div>
            <div><span>Exact potty logs</span><strong>{report.exact_potty_events}</strong></div>
            <div><span>7-day observed coverage</span><strong>{percent(report.observed_coverage_7d)}</strong></div>
          </div>

          <div className="model-table-wrap">
            <table className="model-table">
              <thead>
                <tr><th>Target</th><th>Status</th><th>Positives</th><th>PR-AUC</th><th>ROC-AUC</th><th>Brier</th></tr>
              </thead>
              <tbody>
                {report.models.map((model) => (
                  <tr key={model.target}>
                    <td><strong>{targetLabel(model.target)}</strong><small>baseline {percent(model.prevalence)}</small></td>
                    <td>{model.fitted ? "Fitted" : "Early"}</td>
                    <td>{model.positive_examples}</td>
                    <td>{metric(model.pr_auc)}</td>
                    <td>{metric(model.roc_auc)}</td>
                    <td>{metric(model.brier_score)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {report.top_features.length > 0 && (
            <div className="model-feature-block">
              <span>Strongest learned signals</span>
              <div>{report.top_features.map((feature) => <i key={feature}>{feature}</i>)}</div>
            </div>
          )}

          {report.interval_potty_windows > 0 && (
            <p className="model-footnote">{report.interval_potty_windows} unobserved periods contain pee/poop evidence. They improve data-quality context but are intentionally not assigned fake timestamps for model training.</p>
          )}
        </>
      )}
    </section>
  );
}
