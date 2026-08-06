import { useEffect, useState } from "react";

import "./App.css";
import { DogProfile } from "./components/DogProfile";
import { EventLogger } from "./components/EventLogger";
import { EventTimeline } from "./components/EventTimeline";
import { getDogs } from "./services/api";
import type { Dog } from "./types/dog";
import { getTreatTypes } from "./services/api";
import type { TreatType } from "./types/event";

function App() {
  const [dog, setDog] = useState<Dog | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timelineRefreshKey, setTimelineRefreshKey] = useState(0);
  const [treatTypes, setTreatTypes] = useState<TreatType[]>([]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadDog() {
      try {
        const [dogs, treats] = await Promise.all([
          getDogs(controller.signal),
          getTreatTypes(controller.signal),
        ]);

        setTreatTypes(treats);

        if (dogs.length === 0) {
          throw new Error("No dog profile was found.");
        }

        setDog(dogs[0]);
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") {
          setError(err.message);
        }
      } finally {
        setIsLoading(false);
      }
    }

    void loadDog();

    return () => {
      controller.abort();
    };
  }, []);

  return (
    <main className="app-shell">
      <header className="app-header">
        <p className="brand">PawPredict</p>
        <p className="tagline">Personalized canine behavior tracking</p>
      </header>

      {isLoading && <p className="status-message">Loading Maverick…</p>}

      {error && (
        <div className="error-message" role="alert">
          <strong>Couldn’t load the profile.</strong>
          <span>{error}</span>
        </div>
      )}

      {dog && (
        <>
          <DogProfile dog={dog} />

          <EventLogger
            dogId={dog.id}
            dogName={dog.name}
            onEventSaved={() => {
              setTimelineRefreshKey((current) => current + 1);
            }}
          />

          <EventTimeline
            dogId={dog.id}
            refreshKey={timelineRefreshKey}
            treatTypes={treatTypes}
            onTimelineChanged={() => {
              setTimelineRefreshKey((current) => current + 1);
            }}
          />
        </>
      )}
    </main>
  );
}

export default App;