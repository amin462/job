import { AppShell } from "@/components/layout/AppShell";
import { LandingView } from "@/components/views/LandingView";
import { getCurrentSession } from "@/lib/auth";
import { getLandingData } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const [session, data] = await Promise.all([
    getCurrentSession(),
    getLandingData(),
  ]);

  return (
    <AppShell session={session} publicSummary={data.publicSummary}>
      <LandingView
        publicSummary={data.publicSummary}
        postingVolumeDaily={data.postingVolumeDaily}
        skillDemandWeekly={data.skillDemandWeekly}
        laborMonthly2y={data.laborMonthly2y}
      />
    </AppShell>
  );
}
