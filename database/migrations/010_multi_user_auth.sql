-- PawPredict Phase 7: account ownership + defense-in-depth Supabase RLS.
-- IMPORTANT: this migration intentionally leaves dogs.owner_user_id nullable so
-- an existing single-user dog can be backfilled to the new auth.users UUID.
-- Run 011_enforce_dog_ownership.sql only after every dog has an owner.

begin;

alter table public.dogs
    add column if not exists owner_user_id uuid references auth.users(id) on delete cascade;

create index if not exists idx_dogs_owner_user_id
    on public.dogs (owner_user_id, name);

create or replace function public.user_owns_dog(p_dog_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
    select exists (
        select 1
        from public.dogs d
        where d.id = p_dog_id
          and d.owner_user_id = auth.uid()
    );
$$;

revoke all on function public.user_owns_dog(uuid) from public;
grant execute on function public.user_owns_dog(uuid) to authenticated, service_role;

-- Public-schema reporting views were created before RLS. PostgreSQL views run
-- with the view owner's privileges by default, which can bypass underlying RLS.
-- security_invoker makes direct Supabase REST access honor the caller's RLS
-- policies instead of exposing cross-tenant reporting data.
alter view public.vw_model_registry_overview set (security_invoker = true);
alter view public.vw_model_evaluation_history set (security_invoker = true);
alter view public.vw_model_prediction_monitoring set (security_invoker = true);
alter view public.vw_model_prediction_daily set (security_invoker = true);
alter view public.vw_model_monitoring_history set (security_invoker = true);
alter view public.vw_model_monitoring_latest set (security_invoker = true);
alter view public.vw_model_feature_drift_history set (security_invoker = true);
alter view public.vw_model_feature_drift_latest set (security_invoker = true);

-- Dog root record.
alter table public.dogs enable row level security;
drop policy if exists dogs_owner_all on public.dogs;
create policy dogs_owner_all on public.dogs
    for all to authenticated
    using (owner_user_id = auth.uid())
    with check (owner_user_id = auth.uid());

-- Tables with a direct dog_id.
alter table public.events enable row level security;
drop policy if exists events_owner_all on public.events;
create policy events_owner_all on public.events
    for all to authenticated
    using (public.user_owns_dog(dog_id))
    with check (public.user_owns_dog(dog_id));

alter table public.saved_options enable row level security;
drop policy if exists saved_options_owner_all on public.saved_options;
create policy saved_options_owner_all on public.saved_options
    for all to authenticated
    using (public.user_owns_dog(dog_id))
    with check (public.user_owns_dog(dog_id));

alter table public.dog_event_preferences enable row level security;
drop policy if exists dog_event_preferences_owner_all on public.dog_event_preferences;
create policy dog_event_preferences_owner_all on public.dog_event_preferences
    for all to authenticated
    using (public.user_owns_dog(dog_id))
    with check (public.user_owns_dog(dog_id));

alter table public.observation_periods enable row level security;
drop policy if exists observation_periods_owner_all on public.observation_periods;
create policy observation_periods_owner_all on public.observation_periods
    for all to authenticated
    using (public.user_owns_dog(dog_id))
    with check (public.user_owns_dog(dog_id));

alter table public.dog_stat_preferences enable row level security;
drop policy if exists dog_stat_preferences_owner_all on public.dog_stat_preferences;
create policy dog_stat_preferences_owner_all on public.dog_stat_preferences
    for all to authenticated
    using (public.user_owns_dog(dog_id))
    with check (public.user_owns_dog(dog_id));

alter table public.dog_chart_preferences enable row level security;
drop policy if exists dog_chart_preferences_owner_all on public.dog_chart_preferences;
create policy dog_chart_preferences_owner_all on public.dog_chart_preferences
    for all to authenticated
    using (public.user_owns_dog(dog_id))
    with check (public.user_owns_dog(dog_id));

alter table public.dog_ui_preferences enable row level security;
drop policy if exists dog_ui_preferences_owner_all on public.dog_ui_preferences;
create policy dog_ui_preferences_owner_all on public.dog_ui_preferences
    for all to authenticated
    using (public.user_owns_dog(dog_id))
    with check (public.user_owns_dog(dog_id));

alter table public.scheduled_items enable row level security;
drop policy if exists scheduled_items_owner_all on public.scheduled_items;
create policy scheduled_items_owner_all on public.scheduled_items
    for all to authenticated
    using (public.user_owns_dog(dog_id))
    with check (public.user_owns_dog(dog_id));

alter table public.model_versions enable row level security;
drop policy if exists model_versions_owner_all on public.model_versions;
create policy model_versions_owner_all on public.model_versions
    for all to authenticated
    using (public.user_owns_dog(dog_id))
    with check (public.user_owns_dog(dog_id));

alter table public.model_predictions enable row level security;
drop policy if exists model_predictions_owner_all on public.model_predictions;
create policy model_predictions_owner_all on public.model_predictions
    for all to authenticated
    using (public.user_owns_dog(dog_id))
    with check (public.user_owns_dog(dog_id));

alter table public.model_registry_events enable row level security;
drop policy if exists model_registry_events_owner_all on public.model_registry_events;
create policy model_registry_events_owner_all on public.model_registry_events
    for all to authenticated
    using (public.user_owns_dog(dog_id))
    with check (public.user_owns_dog(dog_id));

alter table public.model_monitoring_snapshots enable row level security;
drop policy if exists model_monitoring_snapshots_owner_all on public.model_monitoring_snapshots;
create policy model_monitoring_snapshots_owner_all on public.model_monitoring_snapshots
    for all to authenticated
    using (public.user_owns_dog(dog_id))
    with check (public.user_owns_dog(dog_id));

alter table public.model_feature_drift enable row level security;
drop policy if exists model_feature_drift_owner_all on public.model_feature_drift;
create policy model_feature_drift_owner_all on public.model_feature_drift
    for all to authenticated
    using (public.user_owns_dog(dog_id))
    with check (public.user_owns_dog(dog_id));

-- Evaluations inherit ownership through their registered model version.
alter table public.model_evaluations enable row level security;
drop policy if exists model_evaluations_owner_all on public.model_evaluations;
create policy model_evaluations_owner_all on public.model_evaluations
    for all to authenticated
    using (
        exists (
            select 1
            from public.model_versions mv
            where mv.id = model_evaluations.model_version_id
              and public.user_owns_dog(mv.dog_id)
        )
    )
    with check (
        exists (
            select 1
            from public.model_versions mv
            where mv.id = model_evaluations.model_version_id
              and public.user_owns_dog(mv.dog_id)
        )
    );

-- PawPredict writes through FastAPI, not directly from the browser. Keep
-- authenticated direct access read-only so clients cannot bypass API-level
-- validation while RLS still protects any direct reads. Anon gets no access to
-- private dog/model data.
revoke all privileges on table
    public.dogs, public.events, public.saved_options,
    public.dog_event_preferences, public.observation_periods,
    public.dog_stat_preferences, public.dog_chart_preferences,
    public.dog_ui_preferences, public.scheduled_items,
    public.model_versions, public.model_evaluations,
    public.model_registry_events, public.model_predictions,
    public.model_monitoring_snapshots, public.model_feature_drift
from anon;

revoke insert, update, delete, truncate, references, trigger on table
    public.dogs, public.events, public.saved_options,
    public.dog_event_preferences, public.observation_periods,
    public.dog_stat_preferences, public.dog_chart_preferences,
    public.dog_ui_preferences, public.scheduled_items,
    public.model_versions, public.model_evaluations,
    public.model_registry_events, public.model_predictions,
    public.model_monitoring_snapshots, public.model_feature_drift
from authenticated;

grant select on table
    public.dogs, public.events, public.saved_options,
    public.dog_event_preferences, public.observation_periods,
    public.dog_stat_preferences, public.dog_chart_preferences,
    public.dog_ui_preferences, public.scheduled_items,
    public.model_versions, public.model_evaluations,
    public.model_registry_events, public.model_predictions,
    public.model_monitoring_snapshots, public.model_feature_drift
to authenticated;

revoke all privileges on table
    public.vw_model_registry_overview, public.vw_model_evaluation_history,
    public.vw_model_prediction_monitoring, public.vw_model_prediction_daily,
    public.vw_model_monitoring_history, public.vw_model_monitoring_latest,
    public.vw_model_feature_drift_history, public.vw_model_feature_drift_latest
from anon;

grant select on table
    public.vw_model_registry_overview, public.vw_model_evaluation_history,
    public.vw_model_prediction_monitoring, public.vw_model_prediction_daily,
    public.vw_model_monitoring_history, public.vw_model_monitoring_latest,
    public.vw_model_feature_drift_history, public.vw_model_feature_drift_latest
to authenticated;

commit;

-- Backfill example (replace with the UUID from Authentication > Users):
-- update public.dogs
-- set owner_user_id = 'YOUR-SUPABASE-USER-UUID'
-- where id = '7ab62dbc-d719-41d4-950c-e5849ae38ccc';
