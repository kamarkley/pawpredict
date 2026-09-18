import { ActiveSessions } from "../components/ActiveSessions";
import { EventLogger } from "../components/EventLogger";
import { EventTimeline } from "../components/EventTimeline";
import { ManualEventLogger } from "../components/ManualEventLogger";
import { ObservationPeriods } from "../components/ObservationPeriods";
import { PottyPredictionCard } from "../components/PottyPredictionCard";
import type { Dog } from "../types/dog";
import type { EventType, SavedOption } from "../types/event";

const SESSION_CODES = new Set(["SLEEP", "SLEEP_NIGHT", "WALK"]);

interface Props {
  dog: Dog;
  eventTypes: EventType[];
  allEventTypes: EventType[];
  options: SavedOption[];
  timelineKey: number;
  observationKey: number;
  onEventSaved: () => void;
  onObservationChanged: () => void;
  onOptionCreated: (option: SavedOption) => void;
}

export function TodayPage({
  dog,
  eventTypes,
  allEventTypes,
  options,
  timelineKey,
  observationKey,
  onEventSaved,
  onObservationChanged,
  onOptionCreated,
}: Props) {
  const quickLogTypes = eventTypes.filter((eventType) => !SESSION_CODES.has(eventType.code));

  return (
    <>
      <section className="today-hero">
        <div>
          <p className="eyebrow">Today with</p>
          <h1>{dog.name}</h1>
          <p>{dog.breed ?? "Dog"} · {dog.age_in_weeks} weeks old</p>
        </div>
        <a className="secondary-button" href="#settings">Settings</a>
      </section>

      <PottyPredictionCard
        dogId={dog.id}
        dogName={dog.name}
        refreshKey={timelineKey + observationKey}
      />

      <ActiveSessions
        dogId={dog.id}
        eventTypes={eventTypes}
        allEventTypes={allEventTypes}
        refreshKey={timelineKey}
        onEventSaved={onEventSaved}
      />

      <EventLogger
        dogId={dog.id}
        dogName={dog.name}
        eventTypes={quickLogTypes}
        options={options}
        onOptionCreated={onOptionCreated}
        onEventSaved={onEventSaved}
      />

      <ManualEventLogger
        dogId={dog.id}
        dogName={dog.name}
        eventTypes={eventTypes}
        options={options}
        onOptionCreated={onOptionCreated}
        onEventSaved={onEventSaved}
      />

      <ObservationPeriods
        dogId={dog.id}
        options={options}
        refreshKey={observationKey}
        onOptionCreated={onOptionCreated}
        onChanged={onObservationChanged}
      />

      <EventTimeline
        dogId={dog.id}
        refreshKey={timelineKey}
        observationRefreshKey={observationKey}
        eventTypes={allEventTypes}
        options={options}
        onOptionCreated={onOptionCreated}
        onTimelineChanged={onEventSaved}
      />
    </>
  );
}
