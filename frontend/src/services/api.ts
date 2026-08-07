import type { Dog, DogUpdate } from "../types/dog";
import type {
  EventCreate,
  EventPreference,
  EventType,
  EventUpdate,
  LoggedEvent,
  SavedOption,
} from "../types/event";

import type { StatPreference } from "../types/stats";

import type {
  ChartPreference,
  ChartPreferenceUpdate,
  UIPreference,
} from "../types/dashboard";

import type {
  ObservationPeriod,
  ObservationPeriodCreate,
  ObservationPeriodUpdate,
} from "../types/observation";

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

export async function getObservationPeriods(
  dogId: string,
  startTime?: string,
  endTime?: string,
  activeOnly = false,
  signal?: AbortSignal,
): Promise<ObservationPeriod[]> {
  const params = new URLSearchParams({ dog_id: dogId });
  if (startTime) params.set("start_time", startTime);
  if (endTime) params.set("end_time", endTime);
  if (activeOnly) params.set("active_only", "true");
  const response = await fetch(`${API_URL}/observation-periods?${params.toString()}`, { signal });
  if (!response.ok) throw await parseError(response, "Failed to load observation periods.");
  return response.json() as Promise<ObservationPeriod[]>;
}

export async function createObservationPeriod(
  period: ObservationPeriodCreate,
): Promise<ObservationPeriod> {
  const response = await fetch(`${API_URL}/observation-periods`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(period),
  });
  if (!response.ok) throw await parseError(response, "Failed to create observation period.");
  return response.json() as Promise<ObservationPeriod>;
}

export async function updateObservationPeriod(
  periodId: string,
  updates: ObservationPeriodUpdate,
): Promise<ObservationPeriod> {
  const response = await fetch(`${API_URL}/observation-periods/${periodId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!response.ok) throw await parseError(response, "Failed to update observation period.");
  return response.json() as Promise<ObservationPeriod>;
}

export async function endObservationPeriod(periodId: string): Promise<ObservationPeriod> {
  const response = await fetch(`${API_URL}/observation-periods/${periodId}/end`, {
    method: "POST",
  });
  if (!response.ok) throw await parseError(response, "Failed to end observation period.");
  return response.json() as Promise<ObservationPeriod>;
}

export async function deleteObservationPeriod(periodId: string): Promise<void> {
  const response = await fetch(`${API_URL}/observation-periods/${periodId}`, {
    method: "DELETE",
  });
  if (!response.ok) throw await parseError(response, "Failed to delete observation period.");
}

export async function getStatPreferences(
  dogId: string,
  signal?: AbortSignal,
): Promise<StatPreference[]> {
  const response = await fetch(`${API_URL}/dogs/${dogId}/stat-preferences`, { signal });
  if (!response.ok) throw await parseError(response, "Failed to load dashboard preferences.");
  return response.json() as Promise<StatPreference[]>;
}

export async function updateStatPreferences(
  dogId: string,
  statCodes: string[],
): Promise<StatPreference[]> {
  const response = await fetch(`${API_URL}/dogs/${dogId}/stat-preferences`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stat_codes: statCodes }),
  });
  if (!response.ok) throw await parseError(response, "Failed to update dashboard preferences.");
  return response.json() as Promise<StatPreference[]>;
}

export async function getChartPreferences(
  dogId: string,
  signal?: AbortSignal,
): Promise<ChartPreference[]> {
  const response = await fetch(
    `${API_URL}/dogs/${dogId}/chart-preferences`,
    { signal },
  );

  if (!response.ok) {
    throw new Error("Could not load chart preferences.");
  }

  return response.json();
}

export async function updateChartPreferences(
  dogId: string,
  preferences: ChartPreferenceUpdate[],
): Promise<ChartPreference[]> {
  const response = await fetch(
    `${API_URL}/dogs/${dogId}/chart-preferences`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        preferences,
      }),
    },
  );

  if (!response.ok) {
    throw new Error("Could not update chart preferences.");
  }

  return response.json();
}

export async function getUIPreferences(
  dogId: string,
  signal?: AbortSignal,
): Promise<UIPreference> {
  const response = await fetch(
    `${API_URL}/dogs/${dogId}/ui-preferences`,
    { signal },
  );

  if (!response.ok) {
    throw new Error("Could not load appearance preferences.");
  }

  return response.json();
}

export async function updateUIPreferences(
  dogId: string,
  accentColor: string,
): Promise<UIPreference> {
  const response = await fetch(
    `${API_URL}/dogs/${dogId}/ui-preferences`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        accent_color: accentColor,
      }),
    },
  );

  if (!response.ok) {
    throw new Error("Could not update appearance preferences.");
  }

  return response.json();
}
