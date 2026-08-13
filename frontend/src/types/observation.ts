export interface ObservationPeriod {
  id: string;
  dog_id: string;
  start_time: string;
  end_time: string | null;
  status: "OBSERVED" | "UNOBSERVED";
  reason_option_id: string | null;
  reason_name: string | null;
  notes: string | null;
  peed_during: boolean | null;
  pooped_during: boolean | null;
  potty_location: string | null;
  likely_state: "SLEEPING" | "AWAKE" | "MIXED" | "UNKNOWN" | null;
  camera_checked: boolean;
  created_at: string;
}

export interface ObservationPeriodCreate {
  dog_id: string;
  start_time?: string;
  end_time?: string | null;
  reason_option_id: string;
  notes?: string | null;
  peed_during?: boolean | null;
  pooped_during?: boolean | null;
  potty_location?: string | null;
  likely_state?: "SLEEPING" | "AWAKE" | "MIXED" | "UNKNOWN" | null;
  camera_checked?: boolean;
}

export interface ObservationPeriodUpdate {
  start_time?: string;
  end_time?: string | null;
  reason_option_id?: string;
  notes?: string | null;
  peed_during?: boolean | null;
  pooped_during?: boolean | null;
  potty_location?: string | null;
  likely_state?: "SLEEPING" | "AWAKE" | "MIXED" | "UNKNOWN" | null;
  camera_checked?: boolean;
}
