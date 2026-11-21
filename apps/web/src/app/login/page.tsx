import { Suspense } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { LoginView } from "@/components/views/AuthViews";
import { getCurrentSession } from "@/lib/auth";
import { loadSeedMarts } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  const session = await getCurrentSession();
  const seed = loadSeedMarts();

  return (
    <AppShell session={session} publicSummary={seed.public_summary}>
      <Suspense fallback={<div className="glass p-6 text-sm">Loading...</div>}>
        <LoginView />
      </Suspense>
    </AppShell>
  );
}
