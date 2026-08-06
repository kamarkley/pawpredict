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
  dogId: string;
  dogName: string;
}

export function EventLogger({
  dogId,
  dogName,
}: EventLoggerProps) {
  const [eventTypes, setEventTypes] = useState<EventType[]>([]);
  const [treatTypes, setTreatTypes] = useState<TreatType[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<EventType | null>(null);
  const [location, setLocation] =
    useState<EventLocation>("NOT_APPLICABLE");
  const [state, setState] = useState<EventState | null>(null);
  const [treatTypeId, setTreatTypeId] = useState<string>("");
  const [notes, setNotes] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadOptions() {
      try {
        const [eventResults, treatResults] = await Promise.all([
          getEventTypes(controller.signal),
          getTreatTypes(controller.signal),
        ]);

        setEventTypes(eventResults);
        setTreatTypes(treatResults);
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

  function resetForm() {
    setSelectedEvent(null);
    setLocation("NOT_APPLICABLE");
    setState(null);
    setTreatTypeId("");
    setNotes("");
  }

  function selectEvent(eventType: EventType) {
    setSelectedEvent(eventType);
    setLocation("NOT_APPLICABLE");
    setState(null);
    setTreatTypeId("");
    setNotes("");
    setMessage(null);
    setError(null);
  }

  function formIsValid(): boolean {
    if (!selectedEvent) {
      return false;
    }

    if (
      selectedEvent.supports_location &&
      location === "NOT_APPLICABLE"
    ) {
      return false;
    }

    if (selectedEvent.supports_state && state === null) {
      return false;
    }

    if (selectedEvent.supports_treat && !treatTypeId) {
      return false;
    }

    return true;
  }

  async function saveEvent() {
    if (!selectedEvent || !formIsValid()) {
      return;
    }

    setIsSaving(true);
    setError(null);
    setMessage(null);

    try {
      await createEvent({
        dog_id: dogId,
        event_type_id: selectedEvent.id,
        state,
        location,
        treat_type_id: treatTypeId || null,
        notes: notes.trim() || null,
        entry_method: "QUICK_LOG",
      });

      setMessage(`${selectedEvent.display_name} logged successfully.`);
      resetForm();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "The event could not be saved.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="event-logger">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Quick log</p>
          <h2>What did {dogName} do?</h2>
        </div>
      </div>

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

      {isLoading && <p>Loading event options…</p>}

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
                <button
                  className={location === "INSIDE" ? "selected-option" : ""}
                  type="button"
                  onClick={() => setLocation("INSIDE")}
                >
                  Inside
                </button>

                <button
                  className={location === "OUTSIDE" ? "selected-option" : ""}
                  type="button"
                  onClick={() => setLocation("OUTSIDE")}
                >
                  Outside
                </button>
              </div>
            </fieldset>
          )}

          {selectedEvent.supports_state && (
            <fieldset>
              <legend>Session status</legend>

              <div className="option-row">
                <button
                  className={state === "START" ? "selected-option" : ""}
                  type="button"
                  onClick={() => setState("START")}
                >
                  Start
                </button>

                <button
                  className={state === "END" ? "selected-option" : ""}
                  type="button"
                  onClick={() => setState("END")}
                >
                  End
                </button>
              </div>
            </fieldset>
          )}

          {selectedEvent.supports_treat && (
            <label className="field-label">
              Treat
              <select
                value={treatTypeId}
                onChange={(event) => setTreatTypeId(event.target.value)}
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
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Add any useful context"
            />
          </label>

          <div className="form-actions">
            <button
              className="cancel-button"
              type="button"
              onClick={resetForm}
            >
              Cancel
            </button>

            <button
              className="save-button"
              disabled={!formIsValid() || isSaving}
              type="button"
              onClick={() => void saveEvent()}
            >
              {isSaving ? "Saving…" : "Save event"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}