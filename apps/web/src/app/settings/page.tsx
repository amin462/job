import { redirect } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { SettingsView } from "@/components/views/InfoSettingsViews";
import { getCurrentSession } from "@/lib/auth";
import { loadSeedMarts } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const session = await getCurrentSession();
  if (!session) {
    redirect("/login?next=/settings");
  }
  const seed = loadSeedMarts();

  return (
    <AppShell session={session} publicSummary={seed.public_summary}>
      <SettingsView session={session} />
    </AppShell>
  );
}
