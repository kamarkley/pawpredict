import type { Dog } from "../types/dog";
import type {
  EventCreate,
  EventType,
  LoggedEvent,
  TreatType,
} from "../types/event";

const API_URL = import.meta.env.VITE_API_URL;

if (!API_URL) {
  throw new Error("VITE_API_URL is not configured.");
}

export async function getDogs(signal?: AbortSignal): Promise<Dog[]> {
  const response = await fetch(`${API_URL}/dogs`, { signal });

  if (!response.ok) {
    throw new Error(`Failed to load dogs: ${response.status}`);
  }

  return response.json() as Promise<Dog[]>;
}

export async function getEventTypes(
  signal?: AbortSignal,
): Promise<EventType[]> {
  const response = await fetch(`${API_URL}/event-types`, { signal });

  if (!response.ok) {
    throw new Error(`Failed to load event types: ${response.status}`);
  }

  return response.json() as Promise<EventType[]>;
}

export async function getTreatTypes(
  signal?: AbortSignal,
): Promise<TreatType[]> {
  const response = await fetch(`${API_URL}/treat-types`, { signal });

  if (!response.ok) {
    throw new Error(`Failed to load treat types: ${response.status}`);
  }

  return response.json() as Promise<TreatType[]>;
}

export async function createEvent(
  event: EventCreate,
): Promise<LoggedEvent> {
  const response = await fetch(`${API_URL}/events`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(event),
  });

  if (!response.ok) {
    const errorBody = (await response.json()) as {
      detail?: string;
    };

    throw new Error(
      errorBody.detail ?? `Failed to save event: ${response.status}`,
    );
  }

  return response.json() as Promise<LoggedEvent>;
}

export async function getEvents(
  dogId: string,
  startTime: string,
  endTime: string,
  signal?: AbortSignal,
): Promise<LoggedEvent[]> {
  const parameters = new URLSearchParams({
    dog_id: dogId,
    start_time: startTime,
    end_time: endTime,
  });

  const response = await fetch(
    `${API_URL}/events?${parameters.toString()}`,
    { signal },
  );

  if (!response.ok) {
    throw new Error(`Failed to load events: ${response.status}`);
  }

  return response.json() as Promise<LoggedEvent[]>;
}