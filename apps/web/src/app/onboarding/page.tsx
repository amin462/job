import { redirect } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { OnboardingView } from "@/components/views/AuthViews";
import { getCurrentSession } from "@/lib/auth";
import { getSkillCatalogData, getUserSkills } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function OnboardingPage() {
  const session = await getCurrentSession();
  if (!session) {
    redirect("/login?next=/onboarding");
  }

  const [catalog, userSkills] = await Promise.all([
    getSkillCatalogData(),
    getUserSkills(session),
  ]);

  return (
    <AppShell session={session} publicSummary={catalog.publicSummary}>
      <OnboardingView
        session={session}
        locations={catalog.dimLocations}
        occupations={catalog.dimOccupations}
        skillsCatalog={catalog.dimSkills}
        initialSkillKeys={userSkills.map((s) => s.skill_key)}
      />
    </AppShell>
  );
}
