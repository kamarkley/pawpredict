import { useCallback, useEffect, useMemo, useState } from "react";

import "./App.css";
import { AuthScreen } from "./components/AuthScreen";
import { DogOnboarding } from "./components/DogOnboarding";
import { CalendarPage } from "./pages/CalendarPage";
import { InsightsPage } from "./pages/InsightsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TodayPage } from "./pages/TodayPage";
import { getStoredSession, signOut, type AuthSession } from "./services/auth";
import { getDogs, getEventTypes, getSavedOptions, getUIPreferences } from "./services/api";
import type { Dog } from "./types/dog";
import type { EventType, SavedOption } from "./types/event";

type Page = "today" | "calendar" | "insights" | "settings";

function pageFromHash(): Page {
  const value = window.location.hash.replace("#", "");
  return value === "calendar" || value === "insights" || value === "settings" ? value : "today";
}

function App() {
  const [session, setSession] = useState<AuthSession | null>(() => getStoredSession());
  const [page, setPage] = useState<Page>(pageFromHash());
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [dog, setDog] = useState<Dog | null>(null);
  const [eventTypes, setEventTypes] = useState<EventType[]>([]);
  const [allEventTypes, setAllEventTypes] = useState<EventType[]>([]);
  const [options, setOptions] = useState<SavedOption[]>([]);
  const [timelineKey, setTimelineKey] = useState(0);
  const [eventPreferenceKey, setEventPreferenceKey] = useState(0);
  const [statPreferenceKey, setStatPreferenceKey] = useState(0);
  const [observationKey, setObservationKey] = useState(0);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [loading, setLoading] = useState(Boolean(session));
  const [error, setError] = useState<string | null>(null);

  const activeDogStorageKey = useMemo(
    () => session ? `pawpredict.activeDog.${session.user.id}` : "pawpredict.activeDog",
    [session],
  );

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
    const handleAuth = () => setSession(getStoredSession());
    window.addEventListener("pawpredict-auth-changed", handleAuth);
    return () => window.removeEventListener("pawpredict-auth-changed", handleAuth);
  }, []);

  useEffect(() => {
    if (!session) return;
    const controller = new AbortController();
    async function loadDogs() {
      setLoading(true);
      setError(null);
      try {
        const rows = await getDogs(controller.signal);
        if (controller.signal.aborted) return;
        setDogs(rows);
        if (!rows.length) {
          setDog(null);
          setShowOnboarding(true);
          return;
        }
        const storedId = localStorage.getItem(activeDogStorageKey);
        const selected = rows.find((row) => row.id === storedId) ?? rows[0];
        setDog(selected);
        localStorage.setItem(activeDogStorageKey, selected.id);
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") setError(err.message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void loadDogs();
    return () => controller.abort();
  }, [session, activeDogStorageKey]);

  useEffect(() => {
    if (!session || !dog) return;
    const dogId = dog.id;
    const controller = new AbortController();
    async function loadDogData() {
      setError(null);
      try {
        const [types, allTypes, saved] = await Promise.all([
          getEventTypes(dogId, true, controller.signal),
          getEventTypes(undefined, false, controller.signal, true),
          getSavedOptions(dogId, undefined, false, controller.signal),
        ]);
        if (controller.signal.aborted) return;
        setEventTypes(types);
        setAllEventTypes(allTypes);
        setOptions(saved);
        getUIPreferences(dogId, controller.signal).then((ui) => {
          document.documentElement.style.setProperty("--paw-accent", ui.accent_color);
        }).catch(() => undefined);
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") setError(err.message);
      }
    }
    void loadDogData();
    return () => controller.abort();
  }, [session, dog]);

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

  function selectDog(dogId: string) {
    const selected = dogs.find((row) => row.id === dogId);
    if (!selected) return;
    setDog(selected);
    localStorage.setItem(activeDogStorageKey, selected.id);
    setTimelineKey((key) => key + 1);
    setObservationKey((key) => key + 1);
    setEventPreferenceKey((key) => key + 1);
    setStatPreferenceKey((key) => key + 1);
  }

  function dogCreated(created: Dog) {
    setDogs((current) => [...current, created].sort((a, b) => a.name.localeCompare(b.name)));
    setDog(created);
    localStorage.setItem(activeDogStorageKey, created.id);
    setShowOnboarding(false);
    window.location.hash = "#today";
  }

  function dogUpdated(updated: Dog) {
    setDog(updated);
    setDogs((current) => current.map((item) => item.id === updated.id ? updated : item));
  }

  async function logout() {
    await signOut();
    setDogs([]);
    setDog(null);
    setEventTypes([]);
    setAllEventTypes([]);
    setOptions([]);
    setShowOnboarding(false);
    setLoading(false);
    setSession(null);
  }

  if (!session) {
    return <AuthScreen onAuthenticated={(next) => setSession(next)} />;
  }

  return (
    <div className="app-layout">
      <header className="topbar">
        <div><p className="brand">PawPredict</p><p className="tagline">Personalized routine tracking + potty prediction</p></div>
        <div className="account-controls">
          {dog && (
            <label className="dog-switcher">
              <span>🐾</span>
              <select value={dog.id} onChange={(event) => selectDog(event.target.value)} aria-label="Active dog">
                {dogs.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </label>
          )}
          <button className="topbar-action" type="button" onClick={() => setShowOnboarding(true)}>+ Dog</button>
          <button className="topbar-action" type="button" onClick={() => void logout()}>Sign out</button>
        </div>
      </header>

      {dog && !showOnboarding && (
        <nav className="app-nav" aria-label="Primary navigation">
          <a className={page === "today" ? "active" : ""} href="#today"><span>⌂</span>Today</a>
          <a className={page === "calendar" ? "active" : ""} href="#calendar"><span>◫</span>Calendar</a>
          <a className={page === "insights" ? "active" : ""} href="#insights"><span>▥</span>Insights</a>
          <a className={page === "settings" ? "active" : ""} href="#settings"><span>⚙</span>Settings</a>
        </nav>
      )}

      <main className="app-shell">
        {loading && <p className="status-message">Loading PawPredict…</p>}
        {error && <div className="error-message"><strong>Couldn’t load PawPredict.</strong><span>{error}</span></div>}

        {!loading && showOnboarding && (
          <DogOnboarding onCreated={dogCreated} onCancel={dogs.length ? () => setShowOnboarding(false) : undefined} />
        )}

        {dog && !showOnboarding && page === "today" && (
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
        {dog && !showOnboarding && page === "calendar" && (
          <CalendarPage
            dogId={dog.id}
            dogName={dog.name}
            refreshKey={timelineKey + observationKey}
            eventTypes={allEventTypes}
            options={options}
            onOptionCreated={saveOption}
            onTimelineChanged={refreshTimeline}
          />
        )}
        {dog && !showOnboarding && page === "insights" && (
          <InsightsPage
            dogId={dog.id}
            dogBirthDate={dog.birth_date}
            refreshKey={timelineKey}
            preferenceRefreshKey={statPreferenceKey}
          />
        )}
        {dog && !showOnboarding && page === "settings" && (
          <SettingsPage
            dog={dog}
            options={options}
            eventPreferenceKey={eventPreferenceKey}
            statPreferenceKey={statPreferenceKey}
            onDogUpdated={dogUpdated}
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
