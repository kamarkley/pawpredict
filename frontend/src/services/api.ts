import type { Dog } from "../types/dog";

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