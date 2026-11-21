import { redirect } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { AdminSourcesView } from "@/components/views/AdminViews";
import { getCurrentSession } from "@/lib/auth";
import { getAdminData } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function AdminSourcesPage() {
  const session = await getCurrentSession();
  if (!session) redirect("/login?next=/admin/sources");
  const adminData = await getAdminData(session);
  if (!adminData) redirect("/?error=forbidden");

  return (
    <AppShell session={session} publicSummary={adminData.publicSummary}>
      <AdminSourcesView publicSummary={adminData.publicSummary} />
    </AppShell>
  );
}
