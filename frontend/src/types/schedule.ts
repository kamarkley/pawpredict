export type ScheduledItemType =
  | "VET_APPOINTMENT"
  | "GROOMING_APPOINTMENT"
  | "BATH"
  | "MEDICATION"
  | "DAYCARE"
  | "TRAINING"
  | "OTHER";

export interface ScheduledItem {
  id: string;
  dog_id: string;
  title: string;
  item_type: ScheduledItemType;
  scheduled_for: string;
  end_time: string | null;
  location: string | null;
  notes: string | null;
  is_completed: boolean;
  linked_event_id: string | null;
  created_at: string;
}

export interface ScheduledItemCreate {
  dog_id: string;
  title: string;
  item_type: ScheduledItemType;
  scheduled_for: string;
  end_time?: string | null;
  location?: string | null;
  notes?: string | null;
}
