import { AppShell } from "@/components/layout/AppShell";
import { AboutView } from "@/components/views/InfoSettingsViews";
import { getCurrentSession } from "@/lib/auth";
import { loadSeedMarts } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function AboutPage() {
  const session = await getCurrentSession();
  const seed = loadSeedMarts();

  return (
    <AppShell session={session} publicSummary={seed.public_summary}>
      <AboutView publicSummary={seed.public_summary} />
    </AppShell>
  );
}
