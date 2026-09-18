# PawPredict Phase 7/8 Release Notes

## Multi-user productization
- Added Supabase email/password authentication.
- Added account-scoped dog ownership and multi-dog switching.
- Added dog onboarding with seeded event/stat/chart/UI preferences and saved options.
- Removed frontend assumptions about a single hardcoded dog.
- Added FastAPI ownership checks to every API endpoint.
- Added Supabase RLS policies and security-invoker reporting views.

## Tracking UX
- Added reusable historical event editing on Calendar.
- Historical date **and time** can be corrected; edits move to the correct day automatically.
- Historical events can be deleted.
- Today and Calendar use the same event editor.
- Added persistent Nap, Sleep, and Walk START/END sessions with live duration timers.
- Active sessions are rebuilt from stored events after navigation/reload.
- Inactive legacy event types remain available to the historical editor.

## ML product behavior
- New dogs display Learning mode while personalized history accumulates.
- Existing prediction model/cache behavior remains unchanged; event corrections update `updated_at`, which participates in the training-bundle fingerprint.
- Existing registry-driven champions, shadow infrastructure, monitoring, and survival research remain intact.

## Production engineering
- Added request IDs, timing headers, structured request logs, configurable CORS, optional Sentry, and a lightweight rate limiter.
- Added auth/security, middleware, and historical-edit tests.
- Added GitHub Actions CI for backend tests/compile checks and frontend lint/build.
- Added staged ownership migrations and a deployment/runbook document.

## Intentionally deferred
- Paid scheduled monitoring/cron infrastructure.
- Distributed queue/worker infrastructure.
- Distributed rate limiting (the current limiter is per API process).
- Password-reset UX and external pilot administration tooling.
