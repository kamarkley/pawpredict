import { useMemo, useState } from "react";

import { createSavedOption } from "../services/api";
import type { EventState, EventType, SavedOption } from "../types/event";

export interface EventFieldValues {
  state: EventState | null;
  optionId: string;
  numericValue: string;
  unit: string;
  severity: string;
  notes: string;
}

interface EventFieldsProps {
  dogId: string;
  eventType: EventType;
  options: SavedOption[];
  values: EventFieldValues;
  onChange: (values: EventFieldValues) => void;
  onOptionCreated: (option: SavedOption) => void;
}

export function EventFields({
  dogId,
  eventType,
  options,
  values,
  onChange,
  onOptionCreated,
}: EventFieldsProps) {
  const [customOption, setCustomOption] = useState("");
  const [optionError, setOptionError] = useState<string | null>(null);
  const filteredOptions = useMemo(
    () => options.filter((option) => option.category === eventType.option_category && option.is_active),
    [eventType.option_category, options],
  );

  function patch(changes: Partial<EventFieldValues>) {
    onChange({ ...values, ...changes });
  }

  async function addOption() {
    const name = customOption.trim();
    if (!eventType.option_category || !name) return;
    setOptionError(null);
    try {
      const option = await createSavedOption(dogId, eventType.option_category, name);
      onOptionCreated(option);
      patch({ optionId: option.id });
      setCustomOption("");
    } catch (error) {
      setOptionError(error instanceof Error ? error.message : "Could not save option.");
    }
  }

  return (
    <>
      {eventType.supports_state && (
        <fieldset>
          <legend>Status</legend>
          <div className="option-row">
            <button
              className={values.state === "START" ? "selected-option" : ""}
              type="button"
              onClick={() => patch({ state: "START" })}
            >
              {eventType.start_label ?? "Start"}
            </button>
            <button
              className={values.state === "END" ? "selected-option" : ""}
              type="button"
              onClick={() => patch({ state: "END" })}
            >
              {eventType.end_label ?? "End"}
            </button>
          </div>
        </fieldset>
      )}

      {eventType.option_category && (
        <div className="option-picker">
          <label className="field-label">
            {eventType.option_category.replaceAll("_", " ").toLowerCase()}
            <select value={values.optionId} onChange={(event) => patch({ optionId: event.target.value })}>
              <option value="">Choose an option</option>
              {filteredOptions.map((option) => (
                <option key={option.id} value={option.id}>{option.name}</option>
              ))}
            </select>
          </label>
          <div className="inline-create">
            <input
              value={customOption}
              onChange={(event) => setCustomOption(event.target.value)}
              placeholder="Add a new option"
            />
            <button type="button" onClick={() => void addOption()}>Save option</button>
          </div>
          {optionError && <p className="event-error">{optionError}</p>}
        </div>
      )}

      {eventType.supports_numeric && (
        <div className="numeric-row">
          <label className="field-label">
            {eventType.numeric_label ?? "Amount"} <span>Optional</span>
            <input
              type="number"
              min="0"
              step="any"
              value={values.numericValue}
              onChange={(event) => patch({ numericValue: event.target.value })}
            />
          </label>
          <label className="field-label">
            Unit
            <select value={values.unit} onChange={(event) => patch({ unit: event.target.value })}>
              <option value="">Choose unit</option>
              {eventType.allowed_units.map((unit) => <option key={unit} value={unit}>{unit}</option>)}
            </select>
          </label>
        </div>
      )}

      {eventType.supports_severity && (
        <label className="field-label">
          Severity: {values.severity || "—"}/10
          <input
            type="range"
            min="1"
            max="10"
            value={values.severity || "5"}
            onChange={(event) => patch({ severity: event.target.value })}
          />
        </label>
      )}

      <label className="field-label">
        Notes <span>Optional</span>
        <textarea
          maxLength={500}
          rows={3}
          value={values.notes}
          onChange={(event) => patch({ notes: event.target.value })}
          placeholder="Add useful context"
        />
      </label>
    </>
  );
}
