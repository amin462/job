import { AppShell } from "@/components/layout/AppShell";
import { MlLabView } from "@/components/views/MlLabView";
import { getCurrentSession } from "@/lib/auth";
import { getMlLabData } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function MlLabPage() {
  const [session, data] = await Promise.all([
    getCurrentSession(),
    getMlLabData(),
  ]);

  return (
    <AppShell session={session} publicSummary={data.publicSummary}>
      <MlLabView
        publicSummary={data.publicSummary}
        leaderboard={data.leaderboard}
        featureImportance={data.featureImportance}
      />
    </AppShell>
  );
}
