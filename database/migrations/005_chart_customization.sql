-- ============================================================
-- PawPredict
-- Migration 005: chart customization, UI preferences, bath
-- ============================================================


-- ------------------------------------------------------------
-- 1. Add Bath event type
-- ------------------------------------------------------------

INSERT INTO event_types (
    code,
    display_name,
    icon,
    supports_state,
    option_required,
    numeric_required,
    severity_required,
    allowed_units,
    is_active
)
VALUES (
    'BATH',
    'Bath',
    '🛁',
    FALSE,
    FALSE,
    FALSE,
    FALSE,
    ARRAY[]::TEXT[],
    TRUE
)
ON CONFLICT (code) DO NOTHING;


-- ------------------------------------------------------------
-- 2. Enable Bath for existing dogs
-- ------------------------------------------------------------

INSERT INTO dog_event_preferences (
    dog_id,
    event_type_id,
    is_enabled,
    display_order
)
SELECT
    d.id,
    et.id,
    TRUE,
    COALESCE(
        (
            SELECT MAX(dep.display_order) + 1
            FROM dog_event_preferences dep
            WHERE dep.dog_id = d.id
        ),
        1
    )
FROM dogs d
JOIN event_types et
    ON et.code = 'BATH'
WHERE NOT EXISTS (
    SELECT 1
    FROM dog_event_preferences existing
    WHERE existing.dog_id = d.id
      AND existing.event_type_id = et.id
);


-- ------------------------------------------------------------
-- 3. Chart catalog
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS chart_types (
    id BIGSERIAL PRIMARY KEY,

    code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,

    required_event_codes TEXT[] NOT NULL
        DEFAULT ARRAY[]::TEXT[],

    default_enabled BOOLEAN NOT NULL
        DEFAULT FALSE,

    default_order INTEGER NOT NULL
        DEFAULT 0,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW()
);


-- ------------------------------------------------------------
-- 4. Per-dog chart preferences
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dog_chart_preferences (
    dog_id UUID NOT NULL
        REFERENCES dogs(id)
        ON DELETE CASCADE,

    chart_type_id BIGINT NOT NULL
        REFERENCES chart_types(id)
        ON DELETE CASCADE,

    is_enabled BOOLEAN NOT NULL
        DEFAULT TRUE,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    PRIMARY KEY (
        dog_id,
        chart_type_id
    )
);


-- ------------------------------------------------------------
-- 5. Per-dog UI preferences
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dog_ui_preferences (
    dog_id UUID PRIMARY KEY
        REFERENCES dogs(id)
        ON DELETE CASCADE,

    accent_color TEXT NOT NULL
        DEFAULT '#6D63D9',

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    CONSTRAINT valid_accent_color
        CHECK (
            accent_color ~ '^#[0-9A-Fa-f]{6}$'
        )
);


-- ------------------------------------------------------------
-- 6. Seed chart catalog
-- ------------------------------------------------------------

INSERT INTO chart_types (
    code,
    display_name,
    description,
    required_event_codes,
    default_enabled,
    default_order
)
VALUES

(
    'DAILY_ACTIVITY',
    'Activity by day',
    'Total number of logged activities by day.',
    ARRAY[]::TEXT[],
    TRUE,
    1
),

(
    'POTTY_OUTCOMES',
    'Potty outcomes',
    'Breakdown of outside potty, accidents, pee pads, litter boxes, and other potty locations.',
    ARRAY['PEE', 'POOP'],
    TRUE,
    2
),

(
    'POTTY_BY_HOUR',
    'Potty activity by hour',
    'Shows the hours when pee and poop events most commonly occur.',
    ARRAY['PEE', 'POOP'],
    TRUE,
    3
),

(
    'ACCIDENT_TREND',
    'Accident trend',
    'Tracks potty accidents over time.',
    ARRAY['PEE', 'POOP'],
    FALSE,
    4
),

(
    'SLEEP_DURATION',
    'Sleep duration',
    'Daily nap and nighttime sleep duration.',
    ARRAY['SLEEP', 'SLEEP_NIGHT'],
    TRUE,
    5
),

(
    'AVG_NAP_DURATION',
    'Average nap duration',
    'Average completed nap duration by day.',
    ARRAY['SLEEP'],
    FALSE,
    6
),

(
    'ACTIVITY_BY_TIME',
    'Activity by time of day',
    'Compares logged activity during morning, afternoon, evening, and night.',
    ARRAY[]::TEXT[],
    TRUE,
    7
),

(
    'WALK_DISTANCE',
    'Walk distance',
    'Tracks total walk distance by day.',
    ARRAY['WALK'],
    FALSE,
    8
),

(
    'BEHAVIOR_BREAKDOWN',
    'Behavior breakdown',
    'Shows the most frequently recorded behaviors.',
    ARRAY['BEHAVIOR'],
    FALSE,
    9
),

(
    'SYMPTOM_SEVERITY',
    'Symptom severity',
    'Tracks symptom severity over time.',
    ARRAY['SYMPTOM'],
    FALSE,
    10
)

ON CONFLICT (code) DO UPDATE
SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    required_event_codes = EXCLUDED.required_event_codes,
    default_enabled = EXCLUDED.default_enabled,
    default_order = EXCLUDED.default_order;


-- ------------------------------------------------------------
-- 7. Seed chart preferences for existing dogs
-- ------------------------------------------------------------

INSERT INTO dog_chart_preferences (
    dog_id,
    chart_type_id,
    is_enabled,
    display_order
)
SELECT
    d.id,
    ct.id,
    ct.default_enabled,
    ct.default_order
FROM dogs d
CROSS JOIN chart_types ct
WHERE ct.is_active = TRUE
ON CONFLICT (
    dog_id,
    chart_type_id
)
DO NOTHING;


-- ------------------------------------------------------------
-- 8. Seed UI preferences for existing dogs
-- ------------------------------------------------------------

INSERT INTO dog_ui_preferences (
    dog_id,
    accent_color
)
SELECT
    id,
    '#6D63D9'
FROM dogs
ON CONFLICT (dog_id)
DO NOTHING;