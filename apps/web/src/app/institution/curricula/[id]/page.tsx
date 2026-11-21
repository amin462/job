import { redirect } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { CurriculumDetailView } from "@/components/views/InstitutionViews";
import { getCurrentSession } from "@/lib/auth";
import { getSkillCatalogData, getUserCurricula } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function CurriculumDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = await getCurrentSession();
  if (!session) redirect(`/login?next=/institution/curricula/${id}`);
  if (session.role !== "institution" && session.role !== "admin") redirect("/?error=forbidden");

  const [catalog, curricula] = await Promise.all([
    getSkillCatalogData(),
    getUserCurricula(session),
  ]);
  const target = curricula.find((c) => String(c.curriculum_id) === id) ?? null;

  return (
    <AppShell session={session} publicSummary={catalog.publicSummary}>
      <CurriculumDetailView
        initialCurriculum={target}
        dimSkills={catalog.dimSkills}
        curriculumCoverageRef={catalog.curriculumCoverageRef}
        publicSummary={catalog.publicSummary}
      />
    </AppShell>
  );
}
