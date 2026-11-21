import { redirect } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { AdminTaxonomyView } from "@/components/views/AdminViews";
import { getCurrentSession } from "@/lib/auth";
import { getAdminData } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function AdminTaxonomyPage() {
  const session = await getCurrentSession();
  if (!session) redirect("/login?next=/admin/taxonomy");
  const adminData = await getAdminData(session);
  if (!adminData) redirect("/?error=forbidden");

  return (
    <AppShell session={session} publicSummary={adminData.publicSummary}>
      <AdminTaxonomyView
        initialPendingAliases={adminData.pendingAliases}
        dimSkills={adminData.dimSkills}
        publicSummary={adminData.publicSummary}
      />
    </AppShell>
  );
}
