-- PawPredict Phase 4: production model monitoring + live drift detection
-- Depends on:
--   model_versions (Phase 1)
--   model_predictions (Phase 2/3)

create table if not exists model_monitoring_snapshots (
    id uuid primary key default gen_random_uuid(),
    dog_id uuid not null references dogs(id) on delete cascade,
    model_version_id uuid not null references model_versions(id) on delete cascade,
    target text not null check (target in ('ANY', 'PEE', 'POOP')),
    lifecycle_status text not null,

    as_of_date date not null,
    as_of_time timestamptz not null,
    window_days integer not null check (window_days > 0),
    recent_start timestamptz not null,
    recent_end timestamptz not null,
    reference_start timestamptz not null,
    reference_end timestamptz not null,

    prediction_count integer not null default 0,
    resolved_count integer not null default 0,
    ineligible_count integer not null default 0,
    pending_count integer not null default 0,
    coverage_rate double precision,
    positive_count integer not null default 0,
    observed_positive_rate double precision,
    avg_probability double precision,
    brier_score double precision,
    ece double precision,
    calibration_gap double precision,

    reference_prediction_count integer not null default 0,
    reference_resolved_count integer not null default 0,
    reference_positive_count integer not null default 0,
    reference_observed_positive_rate double precision,
    reference_brier_score double precision,

    brier_delta double precision,
    brier_relative_change double precision,
    prevalence_delta double precision,
    prediction_psi double precision,
    max_feature_psi double precision,

    performance_status text not null check (
        performance_status in ('HEALTHY', 'WATCH', 'DEGRADED', 'INSUFFICIENT_DATA')
    ),
    drift_status text not null check (
        drift_status in ('HEALTHY', 'WATCH', 'DEGRADED', 'INSUFFICIENT_DATA')
    ),
    health_status text not null check (
        health_status in ('HEALTHY', 'WATCH', 'DEGRADED', 'INSUFFICIENT_DATA')
    ),
    health_reasons jsonb not null default '[]'::jsonb,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    unique (model_version_id, as_of_date, window_days)
);

create index if not exists ix_model_monitoring_snapshots_dog_target_date
    on model_monitoring_snapshots (dog_id, target, as_of_date desc);

create index if not exists ix_model_monitoring_snapshots_model_window_date
    on model_monitoring_snapshots (model_version_id, window_days, as_of_date desc);

create index if not exists ix_model_monitoring_snapshots_health
    on model_monitoring_snapshots (health_status, as_of_date desc);


create table if not exists model_feature_drift (
    id uuid primary key default gen_random_uuid(),
    monitoring_snapshot_id uuid not null references model_monitoring_snapshots(id) on delete cascade,
    dog_id uuid not null references dogs(id) on delete cascade,
    model_version_id uuid not null references model_versions(id) on delete cascade,
    target text not null check (target in ('ANY', 'PEE', 'POOP')),
    feature_name text not null,

    recent_count integer not null default 0,
    reference_count integer not null default 0,
    recent_mean double precision,
    reference_mean double precision,
    recent_std double precision,
    reference_std double precision,
    psi double precision,
    drift_status text not null check (
        drift_status in ('HEALTHY', 'WATCH', 'DEGRADED', 'INSUFFICIENT_DATA')
    ),

    created_at timestamptz not null default now(),

    unique (monitoring_snapshot_id, feature_name)
);

create index if not exists ix_model_feature_drift_model_feature
    on model_feature_drift (model_version_id, feature_name, created_at desc);

create index if not exists ix_model_feature_drift_status
    on model_feature_drift (drift_status, created_at desc);


-- Historical monitoring view: one row per model version / date / rolling window.
create or replace view vw_model_monitoring_history as
select
    s.id as monitoring_snapshot_id,
    s.dog_id,
    s.model_version_id,
    mv.version_label,
    mv.family as model_family,
    s.target,
    s.lifecycle_status,
    s.as_of_date,
    s.as_of_time,
    s.window_days,
    s.recent_start,
    s.recent_end,
    s.reference_start,
    s.reference_end,
    s.prediction_count,
    s.resolved_count,
    s.ineligible_count,
    s.pending_count,
    s.coverage_rate,
    s.positive_count,
    s.observed_positive_rate,
    s.avg_probability,
    s.brier_score,
    s.ece,
    s.calibration_gap,
    s.reference_prediction_count,
    s.reference_resolved_count,
    s.reference_positive_count,
    s.reference_observed_positive_rate,
    s.reference_brier_score,
    s.brier_delta,
    s.brier_relative_change,
    s.prevalence_delta,
    s.prediction_psi,
    s.max_feature_psi,
    s.performance_status,
    s.drift_status,
    s.health_status,
    s.health_reasons,
    s.created_at,
    s.updated_at
from model_monitoring_snapshots s
join model_versions mv on mv.id = s.model_version_id;


-- Latest snapshot per model version / rolling window. This is the easiest
-- surface for a model-health dashboard and later Power BI model fleet page.
create or replace view vw_model_monitoring_latest as
with ranked as (
    select
        h.*,
        row_number() over (
            partition by h.model_version_id, h.window_days
            order by h.as_of_date desc, h.as_of_time desc
        ) as rn
    from vw_model_monitoring_history h
)
select *
from ranked
where rn = 1;


create or replace view vw_model_feature_drift_history as
select
    f.id as feature_drift_id,
    f.monitoring_snapshot_id,
    f.dog_id,
    f.model_version_id,
    mv.version_label,
    f.target,
    s.lifecycle_status,
    s.as_of_date,
    s.as_of_time,
    s.window_days,
    f.feature_name,
    f.recent_count,
    f.reference_count,
    f.recent_mean,
    f.reference_mean,
    f.recent_std,
    f.reference_std,
    f.psi,
    f.drift_status,
    f.created_at
from model_feature_drift f
join model_monitoring_snapshots s on s.id = f.monitoring_snapshot_id
join model_versions mv on mv.id = f.model_version_id;


create or replace view vw_model_feature_drift_latest as
with ranked as (
    select
        h.*,
        row_number() over (
            partition by h.model_version_id, h.window_days, h.feature_name
            order by h.as_of_date desc, h.as_of_time desc
        ) as rn
    from vw_model_feature_drift_history h
)
select *
from ranked
where rn = 1;
