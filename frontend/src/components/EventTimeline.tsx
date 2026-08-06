import { useEffect, useState } from "react";

import {
  deleteEvent,
  getEvents,
  updateEvent,
} from "../services/api";
import type {
  EventLocation,
  EventState,
  LoggedEvent,
  TreatType,
} from "../types/event";
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
  onTimelineChanged: () => void;
  treatTypes: TreatType[];
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
  onTimelineChanged,
  treatTypes,
}: EventTimelineProps) {
  const [events, setEvents] = useState<LoggedEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editingEvent, setEditingEvent] =
    useState<LoggedEvent | null>(null);
  const [editDateTime, setEditDateTime] = useState("");
  const [editLocation, setEditLocation] =
    useState<EventLocation>("NOT_APPLICABLE");
  const [editState, setEditState] =
    useState<EventState | null>(null);
  const [editTreatTypeId, setEditTreatTypeId] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);

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

  function beginEditing(event: LoggedEvent) {
    const date = new Date(event.event_time);

    const localDateTime = new Date(
      date.getTime() - date.getTimezoneOffset() * 60_000,
    )
      .toISOString()
      .slice(0, 16);

    setEditingEvent(event);
    setEditDateTime(localDateTime);
    setEditLocation(event.location);
    setEditState(event.state);
    setEditTreatTypeId(event.treat_type_id ?? "");
    setEditNotes(event.notes ?? "");
    setError(null);
  }

  function cancelEditing() {
    setEditingEvent(null);
  }

  async function saveEditedEvent() {
    if (!editingEvent || !editDateTime) {
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      await updateEvent(editingEvent.id, {
        event_time: new Date(editDateTime).toISOString(),
        state: editState,
        location: editLocation,
        treat_type_id: editTreatTypeId || null,
        notes: editNotes.trim() || null,
      });

      setEditingEvent(null);
      onTimelineChanged();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "The event could not be updated.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function removeEvent(event: LoggedEvent) {
    const eventTime = new Date(event.event_time).toLocaleTimeString(
      "en-US",
      {
        hour: "numeric",
        minute: "2-digit",
      },
    );

    const confirmed = window.confirm(
      `Delete the ${event.event_type_name} log from ${eventTime}?`,
    );

    if (!confirmed) {
      return;
    }

    setError(null);

    try {
      await deleteEvent(event.id);

      if (editingEvent?.id === event.id) {
        setEditingEvent(null);
      }

      onTimelineChanged();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "The event could not be deleted.",
      );
    }
  }

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

                <div className="timeline-actions">
                  <button
                    type="button"
                    onClick={() => beginEditing(event)}
                  >
                    Edit
                  </button>

                  <button
                    className="delete-action"
                    type="button"
                    onClick={() => void removeEvent(event)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            </li>
          );
        })}
      </ol>

      {editingEvent && (
        <div className="edit-event-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Edit log</p>
              <h3>{editingEvent.event_type_name}</h3>
            </div>
          </div>

          <label className="field-label">
            Date and time
            <input
              type="datetime-local"
              value={editDateTime}
              onChange={(event) =>
                setEditDateTime(event.target.value)
              }
            />
          </label>

          {editingEvent.location !== "NOT_APPLICABLE" && (
            <fieldset>
              <legend>Location</legend>

              <div className="option-row">
                <button
                  className={
                    editLocation === "INSIDE"
                      ? "selected-option"
                      : ""
                  }
                  type="button"
                  onClick={() => setEditLocation("INSIDE")}
                >
                  Inside
                </button>

                <button
                  className={
                    editLocation === "OUTSIDE"
                      ? "selected-option"
                      : ""
                  }
                  type="button"
                  onClick={() => setEditLocation("OUTSIDE")}
                >
                  Outside
                </button>
              </div>
            </fieldset>
          )}

          {editingEvent.state && (
            <fieldset>
              <legend>Session status</legend>

              <div className="option-row">
                <button
                  className={
                    editState === "START"
                      ? "selected-option"
                      : ""
                  }
                  type="button"
                  onClick={() => setEditState("START")}
                >
                  Start
                </button>

                <button
                  className={
                    editState === "END"
                      ? "selected-option"
                      : ""
                  }
                  type="button"
                  onClick={() => setEditState("END")}
                >
                  End
                </button>
              </div>
            </fieldset>
          )}

          {editingEvent.event_type_code === "TREAT" && (
            <label className="field-label">
              Treat
              <select
                value={editTreatTypeId}
                onChange={(event) =>
                  setEditTreatTypeId(event.target.value)
                }
              >
                <option value="">Choose a treat</option>

                {treatTypes.map((treat) => (
                  <option key={treat.id} value={treat.id}>
                    {treat.name}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label className="field-label">
            Notes
            <textarea
              maxLength={500}
              rows={3}
              value={editNotes}
              onChange={(event) =>
                setEditNotes(event.target.value)
              }
            />
          </label>

          <div className="form-actions">
            <button
              className="cancel-button"
              type="button"
              onClick={cancelEditing}
            >
              Cancel
            </button>

            <button
              className="save-button"
              disabled={isSaving || !editDateTime}
              type="button"
              onClick={() => void saveEditedEvent()}
            >
              {isSaving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}