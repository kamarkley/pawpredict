import type { Dog, DogUpdate } from "../types/dog";
import type {
  EventCreate,
  EventPreference,
  EventType,
  EventUpdate,
  LoggedEvent,
  SavedOption,
} from "../types/event";

const API_URL = import.meta.env.VITE_API_URL;
if (!API_URL) throw new Error("VITE_API_URL is not configured.");

async function parseError(response: Response, fallback: string): Promise<Error> {
  try {
    const body = (await response.json()) as { detail?: string };
    return new Error(body.detail ?? fallback);
  } catch {
    return new Error(fallback);
  }
}

export async function getDogs(signal?: AbortSignal): Promise<Dog[]> {
  const response = await fetch(`${API_URL}/dogs`, { signal });
  if (!response.ok) throw await parseError(response, "Failed to load dogs.");
  return response.json() as Promise<Dog[]>;
}

export async function updateDog(dogId: string, updates: DogUpdate): Promise<Dog> {
  const response = await fetch(`${API_URL}/dogs/${dogId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!response.ok) throw await parseError(response, "Failed to update profile.");
  return response.json() as Promise<Dog>;
}

export async function getEventTypes(
  dogId?: string,
  enabledOnly = false,
  signal?: AbortSignal,
): Promise<EventType[]> {
  const params = new URLSearchParams();
  if (dogId) params.set("dog_id", dogId);
  if (enabledOnly) params.set("enabled_only", "true");
  const suffix = params.size ? `?${params.toString()}` : "";
  const response = await fetch(`${API_URL}/event-types${suffix}`, { signal });
  if (!response.ok) throw await parseError(response, "Failed to load event types.");
  return response.json() as Promise<EventType[]>;
}

export async function getEventPreferences(
  dogId: string,
  signal?: AbortSignal,
): Promise<EventPreference[]> {
  const response = await fetch(`${API_URL}/dogs/${dogId}/event-preferences`, { signal });
  if (!response.ok) throw await parseError(response, "Failed to load tracking preferences.");
  return response.json() as Promise<EventPreference[]>;
}

export async function updateEventPreferences(
  dogId: string,
  eventTypeIds: number[],
): Promise<EventPreference[]> {
  const response = await fetch(`${API_URL}/dogs/${dogId}/event-preferences`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_type_ids: eventTypeIds }),
  });
  if (!response.ok) throw await parseError(response, "Failed to update tracking preferences.");
  return response.json() as Promise<EventPreference[]>;
}

export async function getSavedOptions(
  dogId: string,
  category?: string,
  includeInactive = false,
  signal?: AbortSignal,
): Promise<SavedOption[]> {
  const params = new URLSearchParams({ dog_id: dogId });
  if (category) params.set("category", category);
  if (includeInactive) params.set("include_inactive", "true");
  const response = await fetch(`${API_URL}/saved-options?${params.toString()}`, { signal });
  if (!response.ok) throw await parseError(response, "Failed to load saved options.");
  return response.json() as Promise<SavedOption[]>;
}

export async function createSavedOption(
  dogId: string,
  category: string,
  name: string,
): Promise<SavedOption> {
  const response = await fetch(`${API_URL}/saved-options`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dog_id: dogId, category, name }),
  });
  if (!response.ok) throw await parseError(response, "Failed to save option.");
  return response.json() as Promise<SavedOption>;
}

export async function updateSavedOption(
  optionId: string,
  updates: { name?: string; is_active?: boolean },
): Promise<SavedOption> {
  const response = await fetch(`${API_URL}/saved-options/${optionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!response.ok) throw await parseError(response, "Failed to update option.");
  return response.json() as Promise<SavedOption>;
}

export async function createEvent(event: EventCreate): Promise<LoggedEvent> {
  const response = await fetch(`${API_URL}/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(event),
  });
  if (!response.ok) throw await parseError(response, "Failed to save event.");
  return response.json() as Promise<LoggedEvent>;
}

export async function getEvents(
  dogId: string,
  startTime: string,
  endTime: string,
  signal?: AbortSignal,
): Promise<LoggedEvent[]> {
  const params = new URLSearchParams({ dog_id: dogId, start_time: startTime, end_time: endTime });
  const response = await fetch(`${API_URL}/events?${params.toString()}`, { signal });
  if (!response.ok) throw await parseError(response, "Failed to load events.");
  return response.json() as Promise<LoggedEvent[]>;
}

export async function updateEvent(eventId: string, updates: EventUpdate): Promise<LoggedEvent> {
  const response = await fetch(`${API_URL}/events/${eventId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!response.ok) throw await parseError(response, "Failed to update event.");
  return response.json() as Promise<LoggedEvent>;
}

export async function deleteEvent(eventId: string): Promise<void> {
  const response = await fetch(`${API_URL}/events/${eventId}`, { method: "DELETE" });
  if (!response.ok) throw await parseError(response, "Failed to delete event.");
}
