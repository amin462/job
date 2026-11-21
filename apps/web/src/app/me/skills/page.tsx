import { redirect } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { MySkillsView } from "@/components/views/StudentViews";
import { getCurrentSession } from "@/lib/auth";
import { getSkillCatalogData, getUserSkills } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function MySkillsPage() {
  const session = await getCurrentSession();
  if (!session) redirect("/login?next=/me/skills");
  if (session.role !== "student" && session.role !== "admin") redirect("/?error=forbidden");

  const [catalog, userSkills] = await Promise.all([
    getSkillCatalogData(),
    getUserSkills(session),
  ]);

  return (
    <AppShell session={session} publicSummary={catalog.publicSummary}>
      <MySkillsView
        session={session}
        initialSkills={userSkills}
        skillsCatalog={catalog.dimSkills}
        occupationSkillProfile={catalog.occupationSkillProfile}
        publicSummary={catalog.publicSummary}
      />
    </AppShell>
  );
}
