import { DailyStatsDashboard } from "../components/DailyStatsDashboard";

interface Props {
  dogId: string;
  refreshKey: number;
  preferenceRefreshKey: number;
}

export function InsightsPage({ dogId, refreshKey, preferenceRefreshKey }: Props) {
  return <DailyStatsDashboard dogId={dogId} refreshKey={refreshKey} preferenceRefreshKey={preferenceRefreshKey} />;
}
