export interface EventType {
  id: number;
  code: string;
  display_name: string;
  category: string;
  supports_state: boolean;
  supports_location: boolean;
  supports_treat: boolean;
}

export interface TreatType {
  id: string;
  name: string;
  brand: string | null;
}

export type EventState = "START" | "END";
export type EventLocation = "INSIDE" | "OUTSIDE" | "NOT_APPLICABLE";

export interface EventCreate {
  dog_id: string;
  event_type_id: number;
  event_time?: string;
  state: EventState | null;
  location: EventLocation;
  treat_type_id: string | null;
  notes: string | null;
  entry_method: "QUICK_LOG" | "MANUAL";
}

export interface LoggedEvent {
  id: string;
  dog_id: string;
  event_type_id: number;
  event_time: string;
  state: EventState | null;
  location: EventLocation;
  treat_type_id: string | null;
  notes: string | null;
  entry_method: "QUICK_LOG" | "MANUAL";
  created_at: string;
}