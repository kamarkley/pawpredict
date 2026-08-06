import type { Dog } from "../types/dog";
import type { EventType } from "../types/event";

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