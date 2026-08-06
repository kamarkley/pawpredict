export interface EventType {
  id: number;
  code: string;
  display_name: string;
  category: string;
  supports_state: boolean;
  supports_location: boolean;
  supports_treat: boolean;
  option_category: string | null;
  option_required: boolean;
  supports_numeric: boolean;
  numeric_label: string | null;
  numeric_required: boolean;
  allowed_units: string[];
  supports_severity: boolean;
  severity_required: boolean;
  start_label: string | null;
  end_label: string | null;
  default_enabled: boolean;
}

export interface SavedOption {
  id: string;
  dog_id: string;
  category: string;
  name: string;
  is_active: boolean;
}

export interface EventPreference {
  event_type: EventType;
  is_enabled: boolean;
  display_order: number | null;
}

export type EventState = "START" | "END";
export type EventLocation = "INSIDE" | "OUTSIDE" | "NOT_APPLICABLE";

export interface EventCreate {
  dog_id: string;
  event_type_id: number;
  event_time?: string;
  state: EventState | null;
  location: EventLocation;
  option_id: string | null;
  numeric_value: number | null;
  unit: string | null;
  severity: number | null;
  notes: string | null;
  entry_method: "QUICK_LOG" | "MANUAL";
}

export interface EventUpdate {
  event_time?: string;
  state?: EventState | null;
  location?: EventLocation;
  option_id?: string | null;
  numeric_value?: number | null;
  unit?: string | null;
  severity?: number | null;
  notes?: string | null;
}

export interface LoggedEvent {
  id: string;
  dog_id: string;
  event_type_id: number;
  event_type_code: string;
  event_type_name: string;
  event_time: string;
  state: EventState | null;
  location: EventLocation;
  option_id: string | null;
  option_name: string | null;
  numeric_value: string | null;
  unit: string | null;
  severity: number | null;
  notes: string | null;
  entry_method: "QUICK_LOG" | "MANUAL";
  created_at: string;
}
