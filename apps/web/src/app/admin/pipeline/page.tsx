import { redirect } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { AdminPipelineView } from "@/components/views/AdminViews";
import { getCurrentSession } from "@/lib/auth";
import { getAdminData } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function AdminPipelinePage() {
  const session = await getCurrentSession();
  if (!session) redirect("/login?next=/admin/pipeline");
  const adminData = await getAdminData(session);
  if (!adminData) redirect("/?error=forbidden");

  return (
    <AppShell session={session} publicSummary={adminData.publicSummary}>
      <AdminPipelineView
        pipelineStatus={adminData.pipelineStatus}
        postingVolumeDaily={adminData.postingVolumeDaily}
        chatLogs={adminData.chatLogs}
        publicSummary={adminData.publicSummary}
      />
    </AppShell>
  );
}
