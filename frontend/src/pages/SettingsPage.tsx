import { DogProfile } from "../components/DogProfile";
import { OptionManager } from "../components/OptionManager";
import { StatSettings } from "../components/StatSettings";
import { TrackingSettings } from "../components/TrackingSettings";
import { DataExportCard } from "../components/DataExportCard";
import type { Dog } from "../types/dog";
import type { SavedOption } from "../types/event";

interface Props {
  dog: Dog;
  options: SavedOption[];
  eventPreferenceKey: number;
  statPreferenceKey: number;
  onDogUpdated: (dog: Dog) => void;
  onEventPreferencesChanged: () => void;
  onStatPreferencesChanged: () => void;
  onOptionsChanged: () => void;
}

export function SettingsPage({
  dog,
  options,
  eventPreferenceKey,
  statPreferenceKey,
  onDogUpdated,
  onEventPreferencesChanged,
  onStatPreferencesChanged,
  onOptionsChanged,
}: Props) {
  return (
    <>
      <div className="page-heading">
        <div><p className="eyebrow">Personalize</p><h1>Settings</h1><p>Manage the profile, tracking choices, saved options, and dashboard cards.</p></div>
      </div>
      <DogProfile dog={dog} onDogUpdated={onDogUpdated} />
      <TrackingSettings dogId={dog.id} refreshKey={eventPreferenceKey} onChanged={onEventPreferencesChanged} />
      <OptionManager dogId={dog.id} options={options} onOptionsChanged={onOptionsChanged} />
      <StatSettings dogId={dog.id} refreshKey={statPreferenceKey} onChanged={onStatPreferencesChanged} />
      <DataExportCard dogId={dog.id} dogName={dog.name} />
    </>
  );
}
