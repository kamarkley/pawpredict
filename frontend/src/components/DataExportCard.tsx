import { useState } from "react";

import { downloadDogExport } from "../services/api";

interface Props {
  dogId: string;
  dogName: string;
}

export function DataExportCard({ dogId, dogName }: Props) {
  const [exporting, setExporting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function download() {
    setExporting(true);
    setMessage(null);
    try {
      await downloadDogExport(dogId, dogName);
      setMessage("Backup downloaded.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not export data.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <section className="settings-card data-export-card">
      <div className="settings-section-heading">
        <div>
          <p className="eyebrow">Your data</p>
          <h2>Export PawPredict history</h2>
          <p>Download a portable JSON backup containing the profile, every event, observation period, and calendar item.</p>
        </div>
      </div>
      <button className="secondary-button full-width" type="button" disabled={exporting} onClick={() => void download()}>
        {exporting ? "Preparing backup…" : "Download full data backup"}
      </button>
      {message && <p className="settings-helper">{message}</p>}
    </section>
  );
}
