import { useEffect, useState } from "react";

import { getEvents } from "../services/api";
import type { LoggedEvent } from "../types/event";
import { getLocalDayRange } from "../utils/date";

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

interface EventTimelineProps {
  dogId: string;
  refreshKey: number;
}

function getEventDetails(event: LoggedEvent): string[] {
  const details: string[] = [];

  if (event.state) {
    details.push(
      event.state.charAt(0) + event.state.slice(1).toLowerCase(),
    );
  }

  if (event.location !== "NOT_APPLICABLE") {
    details.push(
      event.location.charAt(0) +
        event.location.slice(1).toLowerCase(),
    );
  }

  if (event.treat_name) {
    details.push(event.treat_name);
  }

  return details;
}

export function EventTimeline({
  dogId,
  refreshKey,
}: EventTimelineProps) {
  const [events, setEvents] = useState<LoggedEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadEvents() {
      setIsLoading(true);
      setError(null);

      try {
        const { start, end } = getLocalDayRange();

        const results = await getEvents(
          dogId,
          start,
          end,
          controller.signal,
        );

        setEvents(results);
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") {
          setError(err.message);
        }
      } finally {
        setIsLoading(false);
      }
    }

    void loadEvents();

    return () => controller.abort();
  }, [dogId, refreshKey]);

  return (
    <section className="timeline-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Today</p>
          <h2>Activity timeline</h2>
        </div>

        <span className="timeline-count">
          {events.length} {events.length === 1 ? "event" : "events"}
        </span>
      </div>

      {isLoading && <p>Loading today’s activity…</p>}

      {error && (
        <p className="event-error" role="alert">
          {error}
        </p>
      )}

      {!isLoading && !error && events.length === 0 && (
        <div className="timeline-empty">
          <span aria-hidden="true">🐾</span>
          <p>No events have been logged today.</p>
        </div>
      )}

      <ol className="timeline-list">
        {events.map((event) => {
          const details = getEventDetails(event);

          return (
            <li className="timeline-item" key={event.id}>
              <div className="timeline-icon" aria-hidden="true">
                {EVENT_ICONS[event.event_type_code] ?? "🐾"}
              </div>

              <div className="timeline-content">
                <div className="timeline-event-heading">
                  <strong>{event.event_type_name}</strong>

                  <time dateTime={event.event_time}>
                    {new Date(event.event_time).toLocaleTimeString(
                      "en-US",
                      {
                        hour: "numeric",
                        minute: "2-digit",
                      },
                    )}
                  </time>
                </div>

                {details.length > 0 && (
                  <p className="timeline-details">
                    {details.join(" · ")}
                  </p>
                )}

                {event.notes && (
                  <p className="timeline-notes">{event.notes}</p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}