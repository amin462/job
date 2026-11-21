import { redirect } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { AdminQualityView } from "@/components/views/AdminViews";
import { getCurrentSession } from "@/lib/auth";
import { getAdminData } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function AdminQualityPage() {
  const session = await getCurrentSession();
  if (!session) redirect("/login?next=/admin/quality");
  const adminData = await getAdminData(session);
  if (!adminData) redirect("/?error=forbidden");

  return (
    <AppShell session={session} publicSummary={adminData.publicSummary}>
      <AdminQualityView
        dqSummary={adminData.dqSummary}
        publicSummary={adminData.publicSummary}
      />
    </AppShell>
  );
}
