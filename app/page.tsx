import { Suspense } from "react";

import Dashboard from "@/components/Dashboard";
import forecast from "@/public/data/forecast.json";
import link from "@/public/data/link.json";
import manifest from "@/public/data/manifest.json";
import sensitivities from "@/public/data/sensitivities.json";
import type { Forecast, Link, Manifest, Sensitivities } from "@/lib/types";

// These four artifacts are small (tens of KB) and every render needs them, so
// they are imported at build time. The heat grid and event layer are an order
// of magnitude larger and are fetched by the client instead.
export default function Page() {
  return (
    <Suspense fallback={<div style={{ padding: 24 }}>Loading…</div>}>
      <Dashboard
        sensitivities={sensitivities as unknown as Sensitivities}
        manifest={manifest as unknown as Manifest}
        forecast={forecast as unknown as Forecast}
        link={link as unknown as Link}
      />
    </Suspense>
  );
}
