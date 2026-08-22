# PawPredict 1.0 upgrade notes

This package is intended to replace/merge into the working 0.4 project.

## Database

**No new SQL migration is required for 1.0** if migration `006_calendar_observation_ml.sql` is already applied. The live prediction service trains from the existing `dogs`, `events`, and `observation_periods` tables and does not store model binaries in PostgreSQL.

## Backend

New runtime dependencies were added:

- NumPy
- scikit-learn

After merging:

```bash
cd backend
source ../.venv/bin/activate
pip install -r requirements.txt
python -m fastapi dev app/main.py
```

New API routes:

```text
GET /dogs/{dog_id}/predictions/potty
GET /dogs/{dog_id}/predictions/potty/report
GET /dogs/{dog_id}/export
```

The first prediction request after a backend restart trains the personalized model from the database. The process caches the fitted bundle until event/observation data changes.

## Frontend

```bash
cd frontend
npm install
npm run build
npm run dev
```

The existing `VITE_API_URL` value should be retained in your local/deployment environment.

## Production deployment

1. Push the backend changes so Render installs the updated Python requirements.
2. Confirm `/health` and `/health/database` return healthy responses.
3. In FastAPI Swagger, confirm the three new routes above are present.
4. Push/deploy the frontend to Vercel.
5. Open Today and confirm the PawPredict AI card loads.
6. Open Insights and confirm the Potty prediction model panel loads.
7. Log a pee/poop event and confirm the Today prediction refreshes.

## What the probability means

The main score is the estimated probability that an **exactly timestamped pee or poop** will occur within the next 10 minutes.

If the app does not yet have enough usable positive/negative snapshots, the card says **Early personalized estimate**. Once the minimum training threshold is met, it changes to **Personalized ML model** automatically.

## Important data behavior

- Unobserved windows are not treated as negative potty examples.
- Sleep windows are not treated as negative potty examples.
- `peed_during` / `pooped_during` on an unobserved period remain interval evidence and do not receive fabricated timestamps.
- Nap timing is used only as historical state/context through wake-up timing; PawPredict does not predict naps.
