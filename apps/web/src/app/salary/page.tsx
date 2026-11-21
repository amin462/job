import { AppShell } from "@/components/layout/AppShell";
import { SalaryView } from "@/components/views/SalaryView";
import { getCurrentSession } from "@/lib/auth";
import { getSalaryExplorerData, getUserSkills } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function SalaryPage() {
  const session = await getCurrentSession();
  const [data, userSkills] = await Promise.all([
    getSalaryExplorerData(),
    getUserSkills(session),
  ]);

  return (
    <AppShell session={session} publicSummary={data.publicSummary}>
      <SalaryView
        publicSummary={data.publicSummary}
        salaryStats={data.salaryStats}
        occupationSkillProfile={data.occupationSkillProfile}
        dimOccupations={data.dimOccupations}
        dimLocations={data.dimLocations}
        dimSkills={data.dimSkills}
        userSkills={userSkills}
        defaultOccupation={session?.target_occupation_cluster}
        defaultProvince={session?.province_th}
      />
    </AppShell>
  );
}
