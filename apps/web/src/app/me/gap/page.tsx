import { redirect } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { SkillGapView } from "@/components/views/StudentViews";
import { getCurrentSession } from "@/lib/auth";
import { getSkillCatalogData, getUserSkills } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function SkillGapPage() {
  const session = await getCurrentSession();
  if (!session) redirect("/login?next=/me/gap");
  if (session.role !== "student" && session.role !== "admin") redirect("/?error=forbidden");

  const [catalog, userSkills] = await Promise.all([
    getSkillCatalogData(),
    getUserSkills(session),
  ]);

  return (
    <AppShell session={session} publicSummary={catalog.publicSummary}>
      <SkillGapView
        session={session}
        userSkills={userSkills}
        dimOccupations={catalog.dimOccupations}
        dimLocations={catalog.dimLocations}
        occupationSkillProfile={catalog.occupationSkillProfile}
        topLinks={catalog.topLinks}
        publicSummary={catalog.publicSummary}
      />
    </AppShell>
  );
}
