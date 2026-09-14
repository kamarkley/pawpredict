BEGIN;

-- ============================================================
-- PawPredict ML Model Registry
-- Migration: 006_model_registry.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS model_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dog_id UUID NOT NULL REFERENCES dogs(id) ON DELETE CASCADE,

    target TEXT NOT NULL,
    version_label TEXT NOT NULL,
    model_family TEXT NOT NULL DEFAULT 'logistic_regression',
    status TEXT NOT NULL DEFAULT 'CANDIDATE',

    feature_names TEXT[] NOT NULL,
    training_window_days INTEGER,
    sample_weight_half_life_days DOUBLE PRECISION,
    calibration_method TEXT NOT NULL DEFAULT 'raw',

    trained_through TIMESTAMPTZ,
    training_examples INTEGER,
    positive_examples INTEGER,
    prevalence DOUBLE PRECISION,

    git_commit TEXT,
    artifact_uri TEXT,
    config_json JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT model_versions_target_valid
        CHECK (target IN ('ANY', 'PEE', 'POOP')),

    CONSTRAINT model_versions_status_valid
        CHECK (status IN (
            'CANDIDATE',
            'SHADOW',
            'PRODUCTION',
            'RETIRED',
            'REJECTED'
        )),

    CONSTRAINT model_versions_calibration_valid
        CHECK (calibration_method IN ('raw', 'sigmoid', 'isotonic')),

    CONSTRAINT model_versions_window_positive
        CHECK (training_window_days IS NULL OR training_window_days > 0),

    CONSTRAINT model_versions_half_life_positive
        CHECK (
            sample_weight_half_life_days IS NULL
            OR sample_weight_half_life_days > 0
        ),

    CONSTRAINT model_versions_unique_dog_target_label
        UNIQUE (dog_id, target, version_label)
);

-- PostgreSQL partial unique index = exactly one champion per dog/target.
CREATE UNIQUE INDEX IF NOT EXISTS
    uq_model_versions_one_production_per_target
ON model_versions (dog_id, target)
WHERE status = 'PRODUCTION';


CREATE TABLE IF NOT EXISTS model_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_version_id UUID NOT NULL
        REFERENCES model_versions(id) ON DELETE CASCADE,

    evaluation_key TEXT NOT NULL,
    evaluation_type TEXT NOT NULL,
    window_start TIMESTAMPTZ,
    window_end TIMESTAMPTZ,

    snapshot_count INTEGER,
    positive_count INTEGER,
    prevalence DOUBLE PRECISION,

    pr_auc DOUBLE PRECISION,
    roc_auc DOUBLE PRECISION,
    brier_score DOUBLE PRECISION,
    ece DOUBLE PRECISION,
    calibration_intercept DOUBLE PRECISION,
    calibration_slope DOUBLE PRECISION,

    event_capture_rate DOUBLE PRECISION,
    alert_episodes_per_day DOUBLE PRECISION,
    episode_precision DOUBLE PRECISION,
    alert_threshold DOUBLE PRECISION,

    metrics_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT model_evaluations_type_valid
        CHECK (evaluation_type IN (
            'TRAIN',
            'VALIDATION',
            'ROLLING_BACKTEST',
            'HISTORICAL_CONFIRMATION',
            'PROSPECTIVE_SHADOW',
            'PRODUCTION_MONITORING'
        )),

    CONSTRAINT model_evaluations_unique_key
        UNIQUE (model_version_id, evaluation_key)
);

CREATE INDEX IF NOT EXISTS idx_model_evaluations_version_time
    ON model_evaluations (model_version_id, window_end DESC);


CREATE TABLE IF NOT EXISTS model_registry_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dog_id UUID NOT NULL REFERENCES dogs(id) ON DELETE CASCADE,
    model_version_id UUID REFERENCES model_versions(id) ON DELETE SET NULL,

    target TEXT NOT NULL,
    event_type TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT,
    reason TEXT,
    actor TEXT NOT NULL DEFAULT 'system',
    metadata_json JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_model_registry_events_dog_time
    ON model_registry_events (dog_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_model_registry_events_version
    ON model_registry_events (model_version_id, created_at DESC);


DROP TRIGGER IF EXISTS set_model_versions_updated_at ON model_versions;
CREATE TRIGGER set_model_versions_updated_at
BEFORE UPDATE ON model_versions
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- Power BI-friendly registry overview.
CREATE OR REPLACE VIEW vw_model_registry_overview AS
SELECT
    mv.id AS model_version_id,
    mv.dog_id,
    d.name AS dog_name,
    mv.target,
    mv.version_label,
    mv.model_family,
    mv.status,
    mv.training_window_days,
    mv.sample_weight_half_life_days,
    mv.calibration_method,
    mv.feature_names,
    cardinality(mv.feature_names) AS feature_count,
    mv.trained_through,
    mv.training_examples,
    mv.positive_examples,
    mv.prevalence,
    mv.created_at,
    mv.updated_at
FROM model_versions mv
JOIN dogs d ON d.id = mv.dog_id;


CREATE OR REPLACE VIEW vw_model_evaluation_history AS
SELECT
    me.id AS evaluation_id,
    mv.dog_id,
    d.name AS dog_name,
    mv.target,
    mv.version_label,
    mv.status AS current_status,
    me.evaluation_key,
    me.evaluation_type,
    me.window_start,
    me.window_end,
    me.snapshot_count,
    me.positive_count,
    me.prevalence,
    me.pr_auc,
    me.roc_auc,
    me.brier_score,
    me.ece,
    me.calibration_intercept,
    me.calibration_slope,
    me.event_capture_rate,
    me.alert_episodes_per_day,
    me.episode_precision,
    me.alert_threshold,
    me.created_at
FROM model_evaluations me
JOIN model_versions mv ON mv.id = me.model_version_id
JOIN dogs d ON d.id = mv.dog_id;

COMMIT;
