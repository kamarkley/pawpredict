export interface ChartPreference {
  code: string;
  display_name: string;
  description: string | null;
  required_event_codes: string[];
  is_enabled: boolean;
  display_order: number;
}

export interface ChartPreferenceUpdate {
  code: string;
  is_enabled: boolean;
  display_order: number;
}

export interface UIPreference {
  accent_color: string;
}