export interface EventType {
  id: number;
  code: string;
  display_name: string;
  category: string;
  supports_state: boolean;
  supports_location: boolean;
  supports_treat: boolean;
}