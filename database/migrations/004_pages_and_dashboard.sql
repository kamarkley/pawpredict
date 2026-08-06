BEGIN;

CREATE TABLE IF NOT EXISTS stat_types (
    code TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL,
    default_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    display_order SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS dog_stat_preferences (
    dog_id UUID NOT NULL REFERENCES dogs(id) ON DELETE CASCADE,
    stat_code TEXT NOT NULL REFERENCES stat_types(code) ON DELETE CASCADE,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    display_order SMALLINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (dog_id, stat_code)
);

INSERT INTO stat_types (code, display_name, description, default_enabled, display_order)
VALUES
    ('PEE_COUNT', 'Pees today', 'Total pee logs recorded today.', TRUE, 1),
    ('POOP_COUNT', 'Poops today', 'Total poop logs recorded today.', TRUE, 2),
    ('ACCIDENT_COUNT', 'Accidents today', 'Pee or poop logs marked as accidents.', TRUE, 3),
    ('POTTY_SUCCESS_RATE', 'Potty success rate', 'Share of potty logs completed outside.', TRUE, 4),
    ('SINCE_LAST_PEE', 'Time since last pee', 'Elapsed time since the latest pee log.', TRUE, 5),
    ('SINCE_LAST_POOP', 'Time since last poop', 'Elapsed time since the latest poop log.', FALSE, 6),
    ('NAP_DURATION', 'Nap time', 'Completed nap duration logged today.', TRUE, 7),
    ('SLEEP_DURATION', 'Night sleep', 'Completed nighttime sleep duration logged today.', TRUE, 8),
    ('MEAL_COUNT', 'Meals today', 'Total meal logs recorded today.', TRUE, 9),
    ('TREAT_COUNT', 'Treats today', 'Total treat logs recorded today.', FALSE, 10),
    ('WALK_DISTANCE', 'Walk distance', 'Total logged walk distance today.', TRUE, 11),
    ('SYMPTOM_COUNT', 'Symptoms today', 'Total symptom logs recorded today.', TRUE, 12),
    ('AVG_SYMPTOM_SEVERITY', 'Average symptom severity', 'Average severity of today''s symptom logs.', FALSE, 13),
    ('BEHAVIOR_COUNT', 'Behavior logs', 'Total behavior logs recorded today.', FALSE, 14),
    ('SOCIAL_COUNT', 'Social activities', 'Total social activity logs recorded today.', FALSE, 15),
    ('MEDICATION_COUNT', 'Medications today', 'Total medication logs recorded today.', FALSE, 16),
    ('UNOBSERVED_TIME', 'Unobserved time', 'Total time not directly observed today.', TRUE, 17)
ON CONFLICT (code) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    default_enabled = EXCLUDED.default_enabled,
    display_order = EXCLUDED.display_order;

INSERT INTO dog_stat_preferences (dog_id, stat_code, is_enabled, display_order)
SELECT d.id, st.code, st.default_enabled, st.display_order
FROM dogs d CROSS JOIN stat_types st
ON CONFLICT (dog_id, stat_code) DO NOTHING;

DROP TRIGGER IF EXISTS set_dog_stat_preferences_updated_at ON dog_stat_preferences;
CREATE TRIGGER set_dog_stat_preferences_updated_at
BEFORE UPDATE ON dog_stat_preferences
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
