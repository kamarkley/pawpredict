import { useCallback, useEffect, useState } from "react";

import "./App.css";
import { DogProfile } from "./components/DogProfile";
import { EventLogger } from "./components/EventLogger";
import { EventTimeline } from "./components/EventTimeline";
import { ManualEventLogger } from "./components/ManualEventLogger";
import { OptionManager } from "./components/OptionManager";
import { TrackingSettings } from "./components/TrackingSettings";
import { getDogs, getEventTypes, getSavedOptions } from "./services/api";
import type { Dog } from "./types/dog";
import type { EventType, SavedOption } from "./types/event";

function App() {
  const [dog, setDog] = useState<Dog | null>(null);
  const [eventTypes, setEventTypes] = useState<EventType[]>([]);
  const [allEventTypes, setAllEventTypes] = useState<EventType[]>([]);
  const [options, setOptions] = useState<SavedOption[]>([]);
  const [timelineKey, setTimelineKey] = useState(0);
  const [settingsKey, setSettingsKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reloadOptions = useCallback(async (dogId: string) => {
    setOptions(await getSavedOptions(dogId));
  }, []);

  const reloadEventTypes = useCallback(async (dogId: string) => {
    setEventTypes(await getEventTypes(dogId, true));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const dogs = await getDogs(controller.signal);
        if (!dogs.length) throw new Error("No dog profile found.");
        const currentDog = dogs[0];
        setDog(currentDog);
        const [types, allTypes, saved] = await Promise.all([
          getEventTypes(currentDog.id, true, controller.signal),
          getEventTypes(undefined, false, controller.signal),
          getSavedOptions(currentDog.id, undefined, false, controller.signal),
        ]);
        setEventTypes(types); setAllEventTypes(allTypes); setOptions(saved);
      } catch (err) { if (err instanceof Error && err.name !== "AbortError") setError(err.message); }
      finally { setLoading(false); }
    }
    void load(); return () => controller.abort();
  }, []);

  function refreshTimeline() { setTimelineKey((key) => key + 1); }

  return (
    <main className="app-shell">
      <header className="app-header"><p className="brand">PawPredict</p><p className="tagline">Personalized canine behavior tracking</p></header>
      {loading && <p className="status-message">Loading profile…</p>}
      {error && <div className="error-message"><strong>Couldn’t load PawPredict.</strong><span>{error}</span></div>}
      {dog && <>
        <DogProfile dog={dog} onDogUpdated={setDog} />
        <TrackingSettings dogId={dog.id} refreshKey={settingsKey} onChanged={() => { setSettingsKey((key) => key + 1); void reloadEventTypes(dog.id); }} />
        <OptionManager dogId={dog.id} options={options} onOptionsChanged={() => void reloadOptions(dog.id)} />
        <EventLogger dogId={dog.id} dogName={dog.name} eventTypes={eventTypes} options={options} onOptionCreated={(option) => setOptions((current) => [...current.filter((item) => item.id !== option.id), option])} onEventSaved={refreshTimeline} />
        <ManualEventLogger dogId={dog.id} dogName={dog.name} eventTypes={eventTypes} options={options} onOptionCreated={(option) => setOptions((current) => [...current.filter((item) => item.id !== option.id), option])} onEventSaved={refreshTimeline} />
        <EventTimeline dogId={dog.id} refreshKey={timelineKey} eventTypes={allEventTypes} options={options} onOptionCreated={(option) => setOptions((current) => [...current.filter((item) => item.id !== option.id), option])} onTimelineChanged={refreshTimeline} />
      </>}
    </main>
  );
}

export default App;
