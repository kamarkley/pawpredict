BEGIN;

ALTER TABLE event_types
    ADD COLUMN IF NOT EXISTS option_category TEXT,
    ADD COLUMN IF NOT EXISTS option_required BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS supports_numeric BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS numeric_label TEXT,
    ADD COLUMN IF NOT EXISTS numeric_required BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS allowed_units TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    ADD COLUMN IF NOT EXISTS supports_severity BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS severity_required BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS start_label TEXT,
    ADD COLUMN IF NOT EXISTS end_label TEXT,
    ADD COLUMN IF NOT EXISTS default_enabled BOOLEAN NOT NULL DEFAULT TRUE;

CREATE TABLE IF NOT EXISTS saved_options (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dog_id UUID NOT NULL REFERENCES dogs(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT saved_options_category_not_blank CHECK (LENGTH(TRIM(category)) > 0),
    CONSTRAINT saved_options_name_not_blank CHECK (LENGTH(TRIM(name)) > 0),
    CONSTRAINT saved_options_unique_name UNIQUE (dog_id, category, name)
);

CREATE TABLE IF NOT EXISTS dog_event_preferences (
    dog_id UUID NOT NULL REFERENCES dogs(id) ON DELETE CASCADE,
    event_type_id SMALLINT NOT NULL REFERENCES event_types(id) ON DELETE CASCADE,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    display_order SMALLINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (dog_id, event_type_id)
);

ALTER TABLE events
    ADD COLUMN IF NOT EXISTS option_id UUID REFERENCES saved_options(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS numeric_value NUMERIC(10, 3),
    ADD COLUMN IF NOT EXISTS unit TEXT,
    ADD COLUMN IF NOT EXISTS severity SMALLINT;

ALTER TABLE events DROP CONSTRAINT IF EXISTS events_severity_range;
ALTER TABLE events ADD CONSTRAINT events_severity_range
    CHECK (severity IS NULL OR severity BETWEEN 1 AND 10);

CREATE INDEX IF NOT EXISTS idx_saved_options_dog_category
    ON saved_options (dog_id, category, is_active, name);
CREATE INDEX IF NOT EXISTS idx_events_option_id
    ON events (option_id) WHERE option_id IS NOT NULL;

DROP TRIGGER IF EXISTS set_saved_options_updated_at ON saved_options;
CREATE TRIGGER set_saved_options_updated_at
BEFORE UPDATE ON saved_options
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS set_dog_event_preferences_updated_at ON dog_event_preferences;
CREATE TRIGGER set_dog_event_preferences_updated_at
BEFORE UPDATE ON dog_event_preferences
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Update existing event definitions.
UPDATE event_types SET
    option_category = 'POTTY_RESULT', option_required = TRUE, supports_location = FALSE
WHERE code IN ('PEE', 'POOP');

UPDATE event_types SET
    display_name = 'Nap', category = 'REST', supports_state = TRUE,
    option_category = 'SLEEP_LOCATION', option_required = FALSE, start_label = 'Nap start', end_label = 'Nap end'
WHERE code = 'SLEEP';

UPDATE event_types SET
    option_category = 'MEAL_AMOUNT', option_required = TRUE
WHERE code = 'MEAL';

UPDATE event_types SET
    option_category = 'TREAT', option_required = TRUE
WHERE code = 'TREAT';

UPDATE event_types SET
    option_category = 'MEDICATION', option_required = TRUE, supports_numeric = TRUE,
    numeric_required = TRUE, numeric_label = 'Dosage', allowed_units = ARRAY['mg','mL','tablet','capsule','dose']
WHERE code = 'MEDICATION';

UPDATE event_types SET is_active = FALSE, default_enabled = FALSE WHERE code = 'VOMIT';

INSERT INTO event_types (
    code, display_name, category, supports_state, supports_location,
    supports_treat, is_active, option_category, option_required, supports_numeric,
    numeric_required, numeric_label, allowed_units, supports_severity, severity_required, start_label,
    end_label, default_enabled
)
VALUES
    ('SLEEP_NIGHT', 'Sleep', 'REST', TRUE, FALSE, FALSE, TRUE,
     'SLEEP_LOCATION', FALSE, FALSE, FALSE, NULL, ARRAY[]::TEXT[], FALSE, FALSE, 'Go to bed', 'Wake up', TRUE),
    ('WALK', 'Walk', 'ACTIVITY', TRUE, FALSE, FALSE, TRUE,
     NULL, FALSE, TRUE, FALSE, 'Distance', ARRAY['miles','kilometers'], FALSE, FALSE, 'Start walk', 'End walk', TRUE),
    ('SYMPTOM', 'Symptom', 'HEALTH', FALSE, FALSE, FALSE, TRUE,
     'SYMPTOM', TRUE, FALSE, FALSE, NULL, ARRAY[]::TEXT[], TRUE, TRUE, NULL, NULL, TRUE),
    ('SOCIAL', 'Social', 'ACTIVITY', FALSE, FALSE, FALSE, TRUE,
     'SOCIAL_ACTIVITY', TRUE, FALSE, FALSE, NULL, ARRAY[]::TEXT[], FALSE, FALSE, NULL, NULL, TRUE),
    ('BEHAVIOR', 'Behavior', 'BEHAVIOR', FALSE, FALSE, FALSE, TRUE,
     'BEHAVIOR', TRUE, FALSE, FALSE, NULL, ARRAY[]::TEXT[], FALSE, FALSE, NULL, NULL, TRUE),
    ('GROOMING', 'Grooming', 'CARE', FALSE, FALSE, FALSE, TRUE,
     'GROOMING', TRUE, FALSE, FALSE, NULL, ARRAY[]::TEXT[], FALSE, FALSE, NULL, NULL, FALSE),
    ('VET_VISIT', 'Vet visit', 'HEALTH', FALSE, FALSE, FALSE, TRUE,
     'VET_VISIT', TRUE, FALSE, FALSE, NULL, ARRAY[]::TEXT[], FALSE, FALSE, NULL, NULL, FALSE)
ON CONFLICT (code) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    category = EXCLUDED.category,
    supports_state = EXCLUDED.supports_state,
    option_category = EXCLUDED.option_category,
    option_required = EXCLUDED.option_required,
    supports_numeric = EXCLUDED.supports_numeric,
    numeric_required = EXCLUDED.numeric_required,
    numeric_label = EXCLUDED.numeric_label,
    allowed_units = EXCLUDED.allowed_units,
    supports_severity = EXCLUDED.supports_severity,
    severity_required = EXCLUDED.severity_required,
    start_label = EXCLUDED.start_label,
    end_label = EXCLUDED.end_label,
    default_enabled = EXCLUDED.default_enabled,
    is_active = TRUE;

-- Give every dog preferences for every active event.
INSERT INTO dog_event_preferences (dog_id, event_type_id, is_enabled, display_order)
SELECT d.id, et.id, et.default_enabled, et.id
FROM dogs d CROSS JOIN event_types et
WHERE et.is_active
ON CONFLICT (dog_id, event_type_id) DO NOTHING;

-- Seed reusable choices for each dog.
INSERT INTO saved_options (dog_id, category, name)
SELECT d.id, seed.category, seed.name
FROM dogs d
CROSS JOIN (VALUES
    ('POTTY_RESULT','Outside'), ('POTTY_RESULT','Accident'),
    ('POTTY_RESULT','Pee pad'), ('POTTY_RESULT','Litter box'),
    ('SLEEP_LOCATION','Crate'), ('SLEEP_LOCATION','Kennel'),
    ('SLEEP_LOCATION','Dog bed'), ('SLEEP_LOCATION','Couch'),
    ('SLEEP_LOCATION','Owner''s bed'),
    ('SYMPTOM','Vomiting'), ('SYMPTOM','Diarrhea'),
    ('SYMPTOM','Coughing'), ('SYMPTOM','Itching'),
    ('SYMPTOM','Lethargy'), ('SYMPTOM','Loss of appetite'),
    ('SOCIAL_ACTIVITY','Dog park'), ('SOCIAL_ACTIVITY','Daycare'),
    ('SOCIAL_ACTIVITY','Training class'), ('SOCIAL_ACTIVITY','Playdate'),
    ('SOCIAL_ACTIVITY','Public outing'),
    ('BEHAVIOR','Barking'), ('BEHAVIOR','Chewing'),
    ('BEHAVIOR','Biting'), ('BEHAVIOR','Whining'),
    ('BEHAVIOR','Separation distress'), ('BEHAVIOR','Calm behavior'),
    ('BEHAVIOR','Successful settling'),
    ('GROOMING','Bath'), ('GROOMING','Brushing'), ('GROOMING','Nail trim')
) AS seed(category, name)
ON CONFLICT (dog_id, category, name) DO NOTHING;

-- Copy existing treats into the unified saved option system.
INSERT INTO saved_options (dog_id, category, name)
SELECT d.id, 'TREAT', t.name
FROM dogs d CROSS JOIN treat_types t
WHERE t.is_active
ON CONFLICT (dog_id, category, name) DO NOTHING;

COMMIT;
