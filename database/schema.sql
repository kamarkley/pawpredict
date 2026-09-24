-- ============================================================
-- PawPredict PostgreSQL Schema
-- Version: 0.1.0
-- Purpose: Store dog profiles, behavioral events, treat options,
--          and periods when behavior was not observed.
-- ============================================================

-- Enable UUID generation.
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ============================================================
-- ENUM TYPES
-- ============================================================

CREATE TYPE dog_sex AS ENUM (
    'MALE',
    'FEMALE',
    'UNKNOWN'
);

CREATE TYPE event_state AS ENUM (
    'START',
    'END'
);

CREATE TYPE event_location AS ENUM (
    'INSIDE',
    'OUTSIDE',
    'NOT_APPLICABLE'
);

CREATE TYPE entry_method AS ENUM (
    'QUICK_LOG',
    'MANUAL'
);

CREATE TYPE observation_status AS ENUM (
    'OBSERVED',
    'PARTIALLY_OBSERVED',
    'UNOBSERVED'
);


-- ============================================================
-- DOGS
-- ============================================================

CREATE TABLE dogs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    birth_date DATE NOT NULL,
    breed TEXT,
    sex dog_sex NOT NULL DEFAULT 'UNKNOWN',
    weight_lbs NUMERIC(5, 2),
    neutered BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT dogs_name_not_blank
        CHECK (LENGTH(TRIM(name)) > 0),

    CONSTRAINT dogs_weight_positive
        CHECK (weight_lbs IS NULL OR weight_lbs > 0),

    CONSTRAINT dogs_birth_date_valid
        CHECK (birth_date <= CURRENT_DATE)
);


-- ============================================================
-- EVENT TYPES
-- ============================================================

CREATE TABLE event_types (
    id SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    supports_state BOOLEAN NOT NULL DEFAULT FALSE,
    supports_location BOOLEAN NOT NULL DEFAULT FALSE,
    supports_treat BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT event_types_code_format
        CHECK (code ~ '^[A-Z][A-Z0-9_]*$'),

    CONSTRAINT event_types_display_name_not_blank
        CHECK (LENGTH(TRIM(display_name)) > 0),

    CONSTRAINT event_types_category_not_blank
        CHECK (LENGTH(TRIM(category)) > 0)
);


-- ============================================================
-- TREAT TYPES
-- ============================================================

CREATE TABLE treat_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    brand TEXT,
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT treat_types_name_not_blank
        CHECK (LENGTH(TRIM(name)) > 0)
);


-- ============================================================
-- EVENTS
-- ============================================================

CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dog_id UUID NOT NULL,
    event_type_id SMALLINT NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    state event_state,
    location event_location NOT NULL DEFAULT 'NOT_APPLICABLE',
    treat_type_id UUID,
    notes TEXT,
    entry_method entry_method NOT NULL DEFAULT 'QUICK_LOG',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT events_dog_fk
        FOREIGN KEY (dog_id)
        REFERENCES dogs(id)
        ON DELETE CASCADE,

    CONSTRAINT events_event_type_fk
        FOREIGN KEY (event_type_id)
        REFERENCES event_types(id)
        ON DELETE RESTRICT,

    CONSTRAINT events_treat_type_fk
        FOREIGN KEY (treat_type_id)
        REFERENCES treat_types(id)
        ON DELETE SET NULL,

    CONSTRAINT events_time_not_unreasonably_future
        CHECK (event_time <= NOW() + INTERVAL '5 minutes')
);


-- ============================================================
-- OBSERVATION PERIODS
-- ============================================================

CREATE TABLE observation_periods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dog_id UUID NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    status observation_status NOT NULL DEFAULT 'UNOBSERVED',
    reason TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT observation_periods_dog_fk
        FOREIGN KEY (dog_id)
        REFERENCES dogs(id)
        ON DELETE CASCADE,

    CONSTRAINT observation_periods_valid_range
        CHECK (end_time > start_time)
);


-- ============================================================
-- DAILY NOTES
-- ============================================================

CREATE TABLE daily_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dog_id UUID NOT NULL,
    note_date DATE NOT NULL,
    notes TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT daily_notes_dog_fk
        FOREIGN KEY (dog_id)
        REFERENCES dogs(id)
        ON DELETE CASCADE,

    CONSTRAINT daily_notes_unique_dog_date
        UNIQUE (dog_id, note_date),

    CONSTRAINT daily_notes_not_blank
        CHECK (LENGTH(TRIM(notes)) > 0)
);


-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_events_dog_time
    ON events (dog_id, event_time DESC);

CREATE INDEX idx_events_type_time
    ON events (event_type_id, event_time DESC);

CREATE INDEX idx_events_treat_type
    ON events (treat_type_id)
    WHERE treat_type_id IS NOT NULL;

CREATE INDEX idx_observation_periods_dog_time
    ON observation_periods (dog_id, start_time, end_time);

CREATE INDEX idx_daily_notes_dog_date
    ON daily_notes (dog_id, note_date DESC);


-- ============================================================
-- AUTOMATIC updated_at TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_dogs_updated_at
BEFORE UPDATE ON dogs
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER set_treat_types_updated_at
BEFORE UPDATE ON treat_types
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER set_events_updated_at
BEFORE UPDATE ON events
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER set_observation_periods_updated_at
BEFORE UPDATE ON observation_periods
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER set_daily_notes_updated_at
BEFORE UPDATE ON daily_notes
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


-- ============================================================
-- SEED EVENT TYPES
-- ============================================================

INSERT INTO event_types (
    code,
    display_name,
    category,
    supports_state,
    supports_location,
    supports_treat
)
VALUES
    ('PEE', 'Pee', 'POTTY', FALSE, TRUE, FALSE),
    ('POOP', 'Poop', 'POTTY', FALSE, TRUE, FALSE),
    ('POTTY_ATTEMPT', 'Potty Attempt', 'POTTY', FALSE, FALSE, FALSE),
    ('MEAL', 'Meal', 'NUTRITION', FALSE, FALSE, FALSE),
    ('WATER', 'Water', 'NUTRITION', FALSE, FALSE, FALSE),
    ('TREAT', 'Treat', 'NUTRITION', FALSE, FALSE, TRUE),
    ('SLEEP', 'Sleep', 'REST', TRUE, FALSE, FALSE),
    ('PLAY', 'Play', 'ACTIVITY', TRUE, FALSE, FALSE),
    ('TRAINING', 'Training', 'ACTIVITY', TRUE, FALSE, FALSE),
    ('ZOOMIES', 'Zoomies', 'BEHAVIOR', FALSE, FALSE, FALSE),
    ('VOMIT', 'Vomit', 'HEALTH', FALSE, TRUE, FALSE),
    ('MEDICATION', 'Medication', 'HEALTH', FALSE, FALSE, FALSE);


-- ============================================================
-- SEED MAVERICK
-- ============================================================

INSERT INTO dogs (
    name,
    birth_date,
    breed,
    sex,
    neutered
)
VALUES (
    'Maverick',
    '2026-05-13',
    'Maltipoo',
    'MALE',
    NULL
);


-- ============================================================
-- SEED TREAT OPTIONS
-- ============================================================

INSERT INTO treat_types (name)
VALUES
    ('Pupcicle'),
    ('Dental Chew'),
    ('Training Treat');