import { AppShell } from "@/components/layout/AppShell";
import { MarketView } from "@/components/views/MarketView";
import { getCurrentSession } from "@/lib/auth";
import { getMarketExplorerData } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function MarketPage() {
  const [session, data] = await Promise.all([
    getCurrentSession(),
    getMarketExplorerData(),
  ]);

  return (
    <AppShell
      session={session}
      publicSummary={data.publicSummary}
      locations={data.dimLocations}
      occupations={data.dimOccupations}
      showContextBar
    >
      <MarketView
        publicSummary={data.publicSummary}
        skillDemandWeekly={data.skillDemandWeekly}
        occupationSkillProfile={data.occupationSkillProfile}
        postingVolumeDaily={data.postingVolumeDaily}
        laborMonthly2y={data.laborMonthly2y}
        onetSkillBenchmark={data.onetSkillBenchmark}
      />
    </AppShell>
  );
}
