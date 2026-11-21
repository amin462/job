import { redirect } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { CurriculaListView } from "@/components/views/InstitutionViews";
import { getCurrentSession } from "@/lib/auth";
import { getSkillCatalogData, getUserCurricula } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function CurriculaListPage() {
  const session = await getCurrentSession();
  if (!session) redirect("/login?next=/institution/curricula");
  if (session.role !== "institution" && session.role !== "admin") redirect("/?error=forbidden");

  const [catalog, curricula] = await Promise.all([
    getSkillCatalogData(),
    getUserCurricula(session),
  ]);

  return (
    <AppShell session={session} publicSummary={catalog.publicSummary}>
      <CurriculaListView
        initialCurricula={curricula}
        dimOccupations={catalog.dimOccupations}
        dimSkills={catalog.dimSkills}
        curriculumCoverageRef={catalog.curriculumCoverageRef}
        publicSummary={catalog.publicSummary}
      />
    </AppShell>
  );
}
