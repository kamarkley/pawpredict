import { useEffect, useState } from "react";

import {
  createEvent,
  getEventTypes,
  getTreatTypes,
} from "../services/api";
import type {
  EventLocation,
  EventState,
  EventType,
  TreatType,
} from "../types/event";

interface ManualEventLoggerProps {
  dogId: string;
  dogName: string;
  onEventSaved: () => void;
}

function getCurrentLocalDateTime(): string {
  const now = new Date();

  return new Date(
    now.getTime() - now.getTimezoneOffset() * 60_000,
  )
    .toISOString()
    .slice(0, 16);
}

export function ManualEventLogger({
  dogId,
  dogName,
  onEventSaved,
}: ManualEventLoggerProps) {
  const [eventTypes, setEventTypes] = useState<EventType[]>([]);
  const [treatTypes, setTreatTypes] = useState<TreatType[]>([]);

  const [eventTypeId, setEventTypeId] = useState("");
  const [eventDateTime, setEventDateTime] = useState(
    getCurrentLocalDateTime(),
  );
  const [location, setLocation] =
    useState<EventLocation>("NOT_APPLICABLE");
  const [state, setState] = useState<EventState | null>(null);
  const [treatTypeId, setTreatTypeId] = useState("");
  const [notes, setNotes] = useState("");

  const [isExpanded, setIsExpanded] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedEventType =
    eventTypes.find(
      (eventType) => eventType.id === Number(eventTypeId),
    ) ?? null;

  useEffect(() => {
    const controller = new AbortController();

    async function loadOptions() {
      try {
        const [events, treats] = await Promise.all([
          getEventTypes(controller.signal),
          getTreatTypes(controller.signal),
        ]);

        setEventTypes(events);
        setTreatTypes(treats);
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") {
          setError(err.message);
        }
      } finally {
        setIsLoading(false);
      }
    }

    void loadOptions();

    return () => controller.abort();
  }, []);

  function resetConditionalFields() {
    setLocation("NOT_APPLICABLE");
    setState(null);
    setTreatTypeId("");
  }

  function handleEventTypeChange(value: string) {
    setEventTypeId(value);
    resetConditionalFields();
    setMessage(null);
    setError(null);
  }

  function resetForm() {
    setEventTypeId("");
    setEventDateTime(getCurrentLocalDateTime());
    resetConditionalFields();
    setNotes("");
  }

  function formIsValid(): boolean {
    if (!selectedEventType || !eventDateTime) {
      return false;
    }

    if (
      selectedEventType.supports_location &&
      location === "NOT_APPLICABLE"
    ) {
      return false;
    }

    if (selectedEventType.supports_state && state === null) {
      return false;
    }

    if (selectedEventType.supports_treat && !treatTypeId) {
      return false;
    }

    return true;
  }

  async function saveManualEvent() {
    if (!selectedEventType || !formIsValid()) {
      return;
    }

    setIsSaving(true);
    setMessage(null);
    setError(null);

    try {
      await createEvent({
        dog_id: dogId,
        event_type_id: selectedEventType.id,
        event_time: new Date(eventDateTime).toISOString(),
        state,
        location,
        treat_type_id: treatTypeId || null,
        notes: notes.trim() || null,
        entry_method: "MANUAL",
      });

      setMessage(
        `${selectedEventType.display_name} added to ${dogName}’s timeline.`,
      );

      resetForm();
      onEventSaved();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "The event could not be saved.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="manual-log-card">
      <button
        className="manual-log-toggle"
        type="button"
        aria-expanded={isExpanded}
        onClick={() => setIsExpanded((current) => !current)}
      >
        <span>
          <span className="eyebrow">Backfill an event</span>
          <strong>Add a manual log</strong>
        </span>

        <span aria-hidden="true">
          {isExpanded ? "−" : "+"}
        </span>
      </button>

      {isExpanded && (
        <div className="manual-log-form">
          {isLoading && <p>Loading event options…</p>}

          {message && (
            <p className="success-message" role="status">
              {message}
            </p>
          )}

          {error && (
            <p className="event-error" role="alert">
              {error}
            </p>
          )}

          {!isLoading && (
            <>
              <label className="field-label">
                Event type
                <select
                  value={eventTypeId}
                  onChange={(event) =>
                    handleEventTypeChange(event.target.value)
                  }
                >
                  <option value="">Choose an event</option>

                  {eventTypes.map((eventType) => (
                    <option
                      key={eventType.id}
                      value={eventType.id}
                    >
                      {eventType.display_name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field-label">
                Date and time
                <input
                  type="datetime-local"
                  value={eventDateTime}
                  onChange={(event) =>
                    setEventDateTime(event.target.value)
                  }
                />
              </label>

              {selectedEventType?.supports_location && (
                <fieldset>
                  <legend>Location</legend>

                  <div className="option-row">
                    <button
                      className={
                        location === "INSIDE"
                          ? "selected-option"
                          : ""
                      }
                      type="button"
                      onClick={() => setLocation("INSIDE")}
                    >
                      Inside
                    </button>

                    <button
                      className={
                        location === "OUTSIDE"
                          ? "selected-option"
                          : ""
                      }
                      type="button"
                      onClick={() => setLocation("OUTSIDE")}
                    >
                      Outside
                    </button>
                  </div>
                </fieldset>
              )}

              {selectedEventType?.supports_state && (
                <fieldset>
                  <legend>Session status</legend>

                  <div className="option-row">
                    <button
                      className={
                        state === "START"
                          ? "selected-option"
                          : ""
                      }
                      type="button"
                      onClick={() => setState("START")}
                    >
                      Start
                    </button>

                    <button
                      className={
                        state === "END"
                          ? "selected-option"
                          : ""
                      }
                      type="button"
                      onClick={() => setState("END")}
                    >
                      End
                    </button>
                  </div>
                </fieldset>
              )}

              {selectedEventType?.supports_treat && (
                <label className="field-label">
                  Treat
                  <select
                    value={treatTypeId}
                    onChange={(event) =>
                      setTreatTypeId(event.target.value)
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
                Notes <span>Optional</span>
                <textarea
                  maxLength={500}
                  rows={3}
                  value={notes}
                  onChange={(event) =>
                    setNotes(event.target.value)
                  }
                  placeholder="Add any useful context"
                />
              </label>

              <div className="form-actions">
                <button
                  className="cancel-button"
                  type="button"
                  onClick={resetForm}
                >
                  Clear
                </button>

                <button
                  className="save-button"
                  disabled={!formIsValid() || isSaving}
                  type="button"
                  onClick={() => void saveManualEvent()}
                >
                  {isSaving ? "Saving…" : "Add to timeline"}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}