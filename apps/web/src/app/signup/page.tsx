import { AppShell } from "@/components/layout/AppShell";
import { SignupView } from "@/components/views/AuthViews";
import { getCurrentSession } from "@/lib/auth";
import { loadSeedMarts } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function SignupPage() {
  const session = await getCurrentSession();
  const seed = loadSeedMarts();

  return (
    <AppShell session={session} publicSummary={seed.public_summary}>
      <SignupView />
    </AppShell>
  );
}
