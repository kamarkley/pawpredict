import { useCallback, useEffect, useState } from "react";

import "./App.css";
import { CalendarPage } from "./pages/CalendarPage";
import { InsightsPage } from "./pages/InsightsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TodayPage } from "./pages/TodayPage";
import { getDogs, getEventTypes, getSavedOptions, getUIPreferences } from "./services/api";
import type { Dog } from "./types/dog";
import type { EventType, SavedOption } from "./types/event";

type Page = "today" | "calendar" | "insights" | "settings";

function pageFromHash(): Page {
  const value = window.location.hash.replace("#", "");
  return value === "calendar" || value === "insights" || value === "settings" ? value : "today";
}

function App() {
  const [page, setPage] = useState<Page>(pageFromHash());
  const [dog, setDog] = useState<Dog | null>(null);
  const [eventTypes, setEventTypes] = useState<EventType[]>([]);
  const [allEventTypes, setAllEventTypes] = useState<EventType[]>([]);
  const [options, setOptions] = useState<SavedOption[]>([]);
  const [timelineKey, setTimelineKey] = useState(0);
  const [eventPreferenceKey, setEventPreferenceKey] = useState(0);
  const [statPreferenceKey, setStatPreferenceKey] = useState(0);
  const [observationKey, setObservationKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reloadOptions = useCallback(async (dogId: string) => {
    setOptions(await getSavedOptions(dogId));
  }, []);

  const reloadEventTypes = useCallback(async (dogId: string) => {
    setEventTypes(await getEventTypes(dogId, true));
  }, []);

  useEffect(() => {
    const handleHash = () => setPage(pageFromHash());
    window.addEventListener("hashchange", handleHash);
    if (!window.location.hash) window.history.replaceState(null, "", "#today");
    return () => window.removeEventListener("hashchange", handleHash);
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
        setEventTypes(types);
        setAllEventTypes(allTypes);
        setOptions(saved);
        getUIPreferences(currentDog.id, controller.signal).then((ui) => {
          document.documentElement.style.setProperty("--paw-accent", ui.accent_color);
        }).catch(() => undefined);
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") setError(err.message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, []);

  function refreshTimeline() {
    setTimelineKey((key) => key + 1);
  }

  function refreshObservations() {
    setObservationKey((key) => key + 1);
    setTimelineKey((key) => key + 1);
  }

  function saveOption(option: SavedOption) {
    setOptions((current) => [...current.filter((item) => item.id !== option.id), option]);
  }

  return (
    <div className="app-layout">
      <header className="topbar">
        <div><p className="brand">PawPredict</p><p className="tagline">Personalized canine behavior tracking</p></div>
        {dog && <span className="dog-pill">🐾 {dog.name}</span>}
      </header>

      <nav className="app-nav" aria-label="Primary navigation">
        <a className={page === "today" ? "active" : ""} href="#today"><span>⌂</span>Today</a>
        <a className={page === "calendar" ? "active" : ""} href="#calendar"><span>◫</span>Calendar</a>
        <a className={page === "insights" ? "active" : ""} href="#insights"><span>▥</span>Insights</a>
        <a className={page === "settings" ? "active" : ""} href="#settings"><span>⚙</span>Settings</a>
      </nav>

      <main className="app-shell">
        {loading && <p className="status-message">Loading profile…</p>}
        {error && <div className="error-message"><strong>Couldn’t load PawPredict.</strong><span>{error}</span></div>}
        {dog && page === "today" && (
          <TodayPage
            dog={dog}
            eventTypes={eventTypes}
            allEventTypes={allEventTypes}
            options={options}
            timelineKey={timelineKey}
            observationKey={observationKey}
            onEventSaved={refreshTimeline}
            onObservationChanged={refreshObservations}
            onOptionCreated={saveOption}
          />
        )}
        {dog && page === "calendar" && (
          <CalendarPage dogId={dog.id} dogName={dog.name} refreshKey={timelineKey + observationKey} />
        )}
        {dog && page === "insights" && (
          <InsightsPage
            dogId={dog.id}
            dogBirthDate={dog.birth_date}
            refreshKey={timelineKey}
            preferenceRefreshKey={statPreferenceKey}
          />
        )}
        {dog && page === "settings" && (
          <SettingsPage
            dog={dog}
            options={options}
            eventPreferenceKey={eventPreferenceKey}
            statPreferenceKey={statPreferenceKey}
            onDogUpdated={setDog}
            onEventPreferencesChanged={() => {
              setEventPreferenceKey((key) => key + 1);
              void reloadEventTypes(dog.id);
            }}
            onStatPreferencesChanged={() => setStatPreferenceKey((key) => key + 1)}
            onOptionsChanged={() => void reloadOptions(dog.id)}
          />
        )}
      </main>
    </div>
  );
}

export default App;
