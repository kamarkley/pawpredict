# PawPredict Database

## Overview

PawPredict uses PostgreSQL to store canine behavioral events and observation context.

## Core Tables

### `dogs`

Stores persistent dog profile information. `owner_user_id` links each dog to its Supabase Auth account. Age is calculated from `birth_date` and is not stored directly.

### `event_types`

Defines standardized event names and indicates which optional fields each event
type supports.

### `events`

Stores timestamped behavioral events for each dog.

### `treat_types`

Stores reusable treat options that can be selected when logging a treat.

### `observation_periods`

Stores time periods when the dog's behavior was observed, partially observed,
or unobserved. Work hours are recorded here rather than as dog events.

### `daily_notes`

Stores optional contextual notes for a dog on a particular date.

## Design Principles

- Behavioral events are stored separately from observation context.
- Derived machine learning features are not stored in the raw event table.
- Dog age is calculated from birth date.
- Standardized codes prevent inconsistent event naming.
- UUID primary keys support multi-user and multi-dog operation.
- Dog-owned tables are protected by API ownership checks and Supabase RLS policies.