import { useEffect, useState } from "react";

import { getEventTypes } from "../services/api";
import type { EventType } from "../types/event";

const EVENT_ICONS: Record<string, string> = {
  PEE: "💧",
  POOP: "💩",
  POTTY_ATTEMPT: "🚪",
  MEAL: "🍽️",
  WATER: "🥤",
  TREAT: "🦴",
  SLEEP: "😴",
  PLAY: "🎾",
  TRAINING: "⭐",
  ZOOMIES: "⚡",
  VOMIT: "🤢",
  MEDICATION: "💊",
};

interface EventLoggerProps {
  dogName: string;
}

export function EventLogger({ dogName }: EventLoggerProps) {
  const [eventTypes, setEventTypes] = useState<EventType[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<EventType | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadEventTypes() {
      try {
        const results = await getEventTypes(controller.signal);
        setEventTypes(results);
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") {
          setError(err.message);
        }
      } finally {
        setIsLoading(false);
      }
    }

    void loadEventTypes();

    return () => controller.abort();
  }, []);

  function selectEvent(eventType: EventType) {
    setSelectedEvent(eventType);
  }

  return (
    <section className="event-logger">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Quick log</p>
          <h2>What did {dogName} do?</h2>
        </div>

        <span className="live-time">
          {new Date().toLocaleTimeString("en-US", {
            hour: "numeric",
            minute: "2-digit",
          })}
        </span>
      </div>

      {isLoading && <p>Loading event options…</p>}

      {error && (
        <p className="event-error" role="alert">
          {error}
        </p>
      )}

      <div className="event-button-grid">
        {eventTypes.map((eventType) => (
          <button
            className="event-button"
            key={eventType.id}
            type="button"
            onClick={() => selectEvent(eventType)}
          >
            <span className="event-icon" aria-hidden="true">
              {EVENT_ICONS[eventType.code] ?? "🐾"}
            </span>

            <span>{eventType.display_name}</span>
          </button>
        ))}
      </div>

      {selectedEvent && (
        <div className="event-selection">
          <p>
            Logging: <strong>{selectedEvent.display_name}</strong>
          </p>

          {selectedEvent.supports_location && (
            <fieldset>
              <legend>Where did it happen?</legend>

              <div className="option-row">
                <button type="button">Inside</button>
                <button type="button">Outside</button>
              </div>
            </fieldset>
          )}

          {selectedEvent.supports_state && (
            <fieldset>
              <legend>Session status</legend>

              <div className="option-row">
                <button type="button">Start</button>
                <button type="button">End</button>
              </div>
            </fieldset>
          )}

          {selectedEvent.supports_treat && (
            <p className="helper-text">
              Treat selection will be added in the next step.
            </p>
          )}

          <button
            className="cancel-button"
            type="button"
            onClick={() => setSelectedEvent(null)}
          >
            Cancel
          </button>
        </div>
      )}
    </section>
  );
}