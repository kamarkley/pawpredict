-- PawPredict migration 006: calendar, observation outcomes, and data-quality support

ALTER TABLE observation_periods
  ADD COLUMN IF NOT EXISTS peed_during BOOLEAN,
  ADD COLUMN IF NOT EXISTS pooped_during BOOLEAN,
  ADD COLUMN IF NOT EXISTS potty_location TEXT,
  ADD COLUMN IF NOT EXISTS likely_state TEXT,
  ADD COLUMN IF NOT EXISTS camera_checked BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'observation_likely_state_valid'
  ) THEN
    ALTER TABLE observation_periods
      ADD CONSTRAINT observation_likely_state_valid
      CHECK (likely_state IS NULL OR likely_state IN ('SLEEPING','AWAKE','MIXED','UNKNOWN'));
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS scheduled_items (
  id UUID PRIMARY KEY,
  dog_id UUID NOT NULL REFERENCES dogs(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  item_type TEXT NOT NULL,
  scheduled_for TIMESTAMPTZ NOT NULL,
  end_time TIMESTAMPTZ,
  location TEXT,
  notes TEXT,
  is_completed BOOLEAN NOT NULL DEFAULT FALSE,
  linked_event_id UUID REFERENCES events(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT scheduled_item_type_valid CHECK (
    item_type IN ('VET_APPOINTMENT','GROOMING_APPOINTMENT','BATH','MEDICATION','DAYCARE','TRAINING','OTHER')
  )
);

CREATE INDEX IF NOT EXISTS ix_scheduled_items_dog_time
  ON scheduled_items (dog_id, scheduled_for);
