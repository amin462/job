import { AppShell } from "@/components/layout/AppShell";
import { OccupationDetailView } from "@/components/views/OccupationDetailView";
import { getCurrentSession } from "@/lib/auth";
import { getOccupationDetailData } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function OccupationDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const [session, data] = await Promise.all([
    getCurrentSession(),
    getOccupationDetailData(slug),
  ]);

  return (
    <AppShell session={session} publicSummary={data.publicSummary}>
      <OccupationDetailView
        occupation={data.occupation}
        skills={data.skills}
        salaryStats={data.salaryStats}
        topLinks={data.topLinks}
        publicSummary={data.publicSummary}
      />
    </AppShell>
  );
}
