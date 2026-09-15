BEGIN;

-- ============================================================
-- PawPredict champion/challenger prediction ledger
-- Migration: 008_model_prediction_ledger.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS model_predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dog_id UUID NOT NULL REFERENCES dogs(id) ON DELETE CASCADE,
    model_version_id UUID NOT NULL REFERENCES model_versions(id) ON DELETE RESTRICT,

    target TEXT NOT NULL,
    role TEXT NOT NULL,

    prediction_time TIMESTAMPTZ NOT NULL,
    prediction_bucket_time TIMESTAMPTZ NOT NULL,
    horizon_end TIMESTAMPTZ NOT NULL,
    probability DOUBLE PRECISION NOT NULL,

    feature_snapshot JSONB NOT NULL DEFAULT '{}'::JSONB,

    outcome_status TEXT NOT NULL DEFAULT 'PENDING',
    observed_outcome BOOLEAN,
    outcome_resolved_at TIMESTAMPTZ,
    ineligible_reason TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT model_predictions_target_valid
        CHECK (target IN ('ANY', 'PEE', 'POOP')),

    CONSTRAINT model_predictions_role_valid
        CHECK (role IN ('CHAMPION', 'SHADOW')),

    CONSTRAINT model_predictions_outcome_status_valid
        CHECK (outcome_status IN ('PENDING', 'RESOLVED', 'INELIGIBLE')),

    CONSTRAINT model_predictions_probability_valid
        CHECK (probability >= 0 AND probability <= 1),

    CONSTRAINT model_predictions_unique_bucket
        UNIQUE (
            dog_id,
            model_version_id,
            target,
            role,
            prediction_bucket_time
        )
);

CREATE INDEX IF NOT EXISTS idx_model_predictions_pending
    ON model_predictions (dog_id, outcome_status, horizon_end);

CREATE INDEX IF NOT EXISTS idx_model_predictions_version_time
    ON model_predictions (model_version_id, prediction_time DESC);

CREATE INDEX IF NOT EXISTS idx_model_predictions_dog_target_time
    ON model_predictions (dog_id, target, prediction_time DESC);


-- Detailed Power BI / debugging view.
CREATE OR REPLACE VIEW vw_model_prediction_monitoring AS
SELECT
    mp.id AS prediction_id,
    mp.dog_id,
    d.name AS dog_name,
    mp.model_version_id,
    mv.version_label,
    mv.status AS current_model_status,
    mp.target,
    mp.role,
    mp.prediction_time,
    mp.prediction_bucket_time,
    mp.horizon_end,
    mp.probability,
    mp.outcome_status,
    mp.observed_outcome,
    mp.outcome_resolved_at,
    mp.ineligible_reason,
    mp.created_at
FROM model_predictions mp
JOIN model_versions mv ON mv.id = mp.model_version_id
JOIN dogs d ON d.id = mp.dog_id;


-- Daily monitoring fact table for Power BI.
CREATE OR REPLACE VIEW vw_model_prediction_daily AS
SELECT
    mp.dog_id,
    d.name AS dog_name,
    mp.model_version_id,
    mv.version_label,
    mp.target,
    mp.role,
    DATE(mp.prediction_time AT TIME ZONE 'UTC') AS prediction_date_utc,
    COUNT(*) AS prediction_count,
    COUNT(*) FILTER (WHERE mp.outcome_status = 'RESOLVED') AS resolved_count,
    COUNT(*) FILTER (WHERE mp.outcome_status = 'INELIGIBLE') AS ineligible_count,
    AVG(mp.probability) AS average_probability,
    AVG(
        CASE
            WHEN mp.outcome_status = 'RESOLVED'
            THEN CASE WHEN mp.observed_outcome THEN 1.0 ELSE 0.0 END
        END
    ) AS observed_positive_rate,
    AVG(
        CASE
            WHEN mp.outcome_status = 'RESOLVED'
            THEN POWER(
                mp.probability -
                CASE WHEN mp.observed_outcome THEN 1.0 ELSE 0.0 END,
                2
            )
        END
    ) AS brier_score
FROM model_predictions mp
JOIN model_versions mv ON mv.id = mp.model_version_id
JOIN dogs d ON d.id = mp.dog_id
GROUP BY
    mp.dog_id,
    d.name,
    mp.model_version_id,
    mv.version_label,
    mp.target,
    mp.role,
    DATE(mp.prediction_time AT TIME ZONE 'UTC');

COMMIT;
