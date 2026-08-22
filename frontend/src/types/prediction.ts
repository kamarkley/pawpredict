export type ModelMode = "TRAINED_MODEL" | "EARLY_ESTIMATE";
export type ModelConfidence = "EARLY" | "GROWING" | "STRONG";

export interface PredictionDriver {
  label: string;
  direction: "UP" | "DOWN" | "NEUTRAL";
  detail: string;
}

export interface ForecastPoint {
  minutes_ahead: number;
  probability: number;
}

export interface TargetModelMetrics {
  target: "ANY" | "PEE" | "POOP";
  fitted: boolean;
  training_examples: number;
  positive_examples: number;
  prevalence: number;
  roc_auc: number | null;
  pr_auc: number | null;
  brier_score: number | null;
  precision: number | null;
  recall: number | null;
}

export interface PottyModelReport {
  mode: ModelMode;
  confidence: ModelConfidence;
  confidence_label: string;
  data_days: number;
  exact_potty_events: number;
  interval_potty_windows: number;
  usable_training_examples: number;
  observed_coverage_7d: number;
  generated_at: string;
  models: TargetModelMetrics[];
  top_features: string[];
}

export interface PottyPrediction {
  generated_at: string;
  horizon_minutes: number;
  probability_any: number;
  probability_pee: number;
  probability_poop: number;
  mode: ModelMode;
  confidence: ModelConfidence;
  confidence_label: string;
  recommendation: string;
  currently_sleeping: boolean;
  currently_unobserved: boolean;
  minutes_since_pee: number | null;
  minutes_since_poop: number | null;
  minutes_since_wake: number | null;
  data_days: number;
  training_examples: number;
  exact_potty_events: number;
  drivers: PredictionDriver[];
  forecast: ForecastPoint[];
}
