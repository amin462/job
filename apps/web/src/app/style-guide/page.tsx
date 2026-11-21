import { AppShell } from "@/components/layout/AppShell";
import { StyleGuideView } from "@/components/views/StyleGuideView";
import { getCurrentSession } from "@/lib/auth";
import { loadSeedMarts } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function StyleGuidePage() {
  const session = await getCurrentSession();
  const seed = loadSeedMarts();

  return (
    <AppShell session={session} publicSummary={seed.public_summary}>
      <StyleGuideView />
    </AppShell>
  );
}
