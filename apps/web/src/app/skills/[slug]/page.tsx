import { AppShell } from "@/components/layout/AppShell";
import { SkillDetailView } from "@/components/views/SkillDetailView";
import { getCurrentSession } from "@/lib/auth";
import { getSkillDetailData } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function SkillDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const [session, data] = await Promise.all([
    getCurrentSession(),
    getSkillDetailData(slug),
  ]);

  return (
    <AppShell session={session} publicSummary={data.publicSummary}>
      <SkillDetailView
        skill={data.skill}
        weeklyTrend={data.weeklyTrend}
        occupationsRequesting={data.occupationsRequesting}
        cooccurrence={data.cooccurrence}
        salaryStats={data.salaryStats}
        publicSummary={data.publicSummary}
        session={session}
      />
    </AppShell>
  );
}
