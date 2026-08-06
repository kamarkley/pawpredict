BEGIN;

ALTER TABLE observation_periods
    ALTER COLUMN end_time DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS reason_option_id UUID REFERENCES saved_options(id) ON DELETE SET NULL;

ALTER TABLE observation_periods DROP CONSTRAINT IF EXISTS observation_periods_valid_range;
ALTER TABLE observation_periods ADD CONSTRAINT observation_periods_valid_range
    CHECK (end_time IS NULL OR end_time > start_time);

CREATE INDEX IF NOT EXISTS idx_observation_periods_reason_option
    ON observation_periods (reason_option_id) WHERE reason_option_id IS NOT NULL;

INSERT INTO saved_options (dog_id, category, name)
SELECT d.id, 'OBSERVATION_REASON', seed.name
FROM dogs d
CROSS JOIN (VALUES
    ('Work'), ('Errands'), ('Daycare'), ('Training class'),
    ('With sitter'), ('Boarding'), ('Sleeping'), ('Other')
) AS seed(name)
ON CONFLICT (dog_id, category, name) DO NOTHING;

COMMIT;
