import type {
  CurriculumItem,
  DemoPersonaKey,
  UserSession,
  UserSkill,
} from "@/types/marts";

export interface DemoPersonaSpec {
  key: DemoPersonaKey;
  labelTh: string;
  labelEn: string;
  descriptionTh: string;
  descriptionEn: string;
  role: "student" | "institution" | "admin";
  session: UserSession;
  initialSkills: UserSkill[];
  initialCurricula: CurriculumItem[];
  defaultRedirect: string;
}

export const DEMO_PERSONAS: Record<DemoPersonaKey, DemoPersonaSpec> = {
  student_data: {
    key: "student_data",
    labelTh: "นักศึกษาสาย Data",
    labelEn: "Data Student",
    descriptionTh: "ทักษะเริ่มต้น: Excel, SQL, Python, Communication · เป้าหมาย Data & Analytics",
    descriptionEn: "Starter skills: Excel, SQL, Python, Communication · Target: Data & Analytics",
    role: "student",
    defaultRedirect: "/me/gap",
    session: {
      user_id: "00000000-0000-4000-8000-000000000101",
      email: "demo.student.data@example.com",
      role: "student",
      display_name: "นักศึกษาสาย Data (Demo)",
      province_th: "สงขลา",
      target_occupation_cluster: "Data & Analytics",
      preferred_language: "th",
      is_demo: true,
      persona: "student_data",
    },
    initialSkills: [
      { skill_key: 1, skill_canonical: "Microsoft Excel", skill_slug: "microsoft-excel", skill_name_th: "ไมโครซอฟท์ เอ็กเซล", skill_type: "tool", skill_group: "Office & Productivity", level: 2 },
      { skill_key: 9, skill_canonical: "SQL", skill_slug: "sql", skill_name_th: "ภาษา SQL และฐานข้อมูล", skill_type: "technical", skill_group: "Data & BI", level: 2 },
      { skill_key: 10, skill_canonical: "Python", skill_slug: "python", skill_name_th: "ภาษาไพทอน (Python)", skill_type: "technical", skill_group: "Data & BI", level: 2 },
      { skill_key: 104, skill_canonical: "Communication", skill_slug: "communication", skill_name_th: "ทักษะการสื่อสารและประสานงาน", skill_type: "soft", skill_group: "Soft Skills", level: 2 },
    ],
    initialCurricula: [],
  },
  student_acc: {
    key: "student_acc",
    labelTh: "นักศึกษาสาย Accounting",
    labelEn: "Accounting Student",
    descriptionTh: "ทักษะเริ่มต้น: Accounting, Tax, Excel, Word · เป้าหมาย Accounting & Finance",
    descriptionEn: "Starter skills: Accounting, Tax, Excel, Word · Target: Accounting & Finance",
    role: "student",
    defaultRedirect: "/me/gap",
    session: {
      user_id: "00000000-0000-4000-8000-000000000102",
      email: "demo.student.acc@example.com",
      role: "student",
      display_name: "นักศึกษาสายบัญชี (Demo)",
      province_th: "กรุงเทพมหานคร",
      target_occupation_cluster: "Accounting & Finance",
      preferred_language: "th",
      is_demo: true,
      persona: "student_acc",
    },
    initialSkills: [
      { skill_key: 54, skill_canonical: "Accounting", skill_slug: "accounting", skill_name_th: "การบัญชีและปิดงบ", skill_type: "technical", skill_group: "Accounting & Finance", level: 2 },
      { skill_key: 55, skill_canonical: "Tax", skill_slug: "tax", skill_name_th: "ภาษีอากร (ภ.ง.ด./VAT)", skill_type: "technical", skill_group: "Accounting & Finance", level: 2 },
      { skill_key: 1, skill_canonical: "Microsoft Excel", skill_slug: "microsoft-excel", skill_name_th: "ไมโครซอฟท์ เอ็กเซล", skill_type: "tool", skill_group: "Office & Productivity", level: 2 },
      { skill_key: 2, skill_canonical: "Microsoft Word", skill_slug: "microsoft-word", skill_name_th: "ไมโครซอฟท์ เวิร์ด", skill_type: "tool", skill_group: "Office & Productivity", level: 2 },
    ],
    initialCurricula: [],
  },
  institution: {
    key: "institution",
    labelTh: "อาจารย์หลักสูตร",
    labelEn: "Curriculum Advisor",
    descriptionTh: "มีหลักสูตรตัวอย่าง 'คอมพิวเตอร์ธุรกิจ / Data Analytics' พร้อมรายวิชา",
    descriptionEn: "Pre-seeded with 'Business Computing / Data Analytics' sample curriculum",
    role: "institution",
    defaultRedirect: "/institution/curricula",
    session: {
      user_id: "00000000-0000-4000-8000-000000000103",
      email: "demo.institution@example.com",
      role: "institution",
      display_name: "อาจารย์ผู้ดูแลหลักสูตร (Demo)",
      province_th: "สงขลา",
      target_occupation_cluster: "Data & Analytics",
      preferred_language: "th",
      is_demo: true,
      persona: "institution",
    },
    initialSkills: [],
    initialCurricula: [
      {
        curriculum_id: 1,
        owner_id: "00000000-0000-4000-8000-000000000103",
        name: "หลักสูตรคอมพิวเตอร์ธุรกิจ / Data Analytics (ตัวอย่าง)",
        target_occupation_cluster: "Data & Analytics",
        created_at: "2026-11-18T10:00:00Z",
        skills: [
          { curriculum_id: 1, skill_key: 1, course_name: "คอมพิวเตอร์และเครื่องมือสำนักงาน" },
          { curriculum_id: 1, skill_key: 104, course_name: "คอมพิวเตอร์และเครื่องมือสำนักงาน" },
          { curriculum_id: 1, skill_key: 9, course_name: "การจัดการฐานข้อมูล" },
          { curriculum_id: 1, skill_key: 10, course_name: "การวิเคราะห์ข้อมูลทางธุรกิจ" },
          { curriculum_id: 1, skill_key: 6, course_name: "การวิเคราะห์ข้อมูลทางธุรกิจ" },
        ],
      },
      {
        curriculum_id: 2,
        owner_id: "00000000-0000-4000-8000-000000000103",
        name: "หลักสูตรบัญชีดิจิทัล (ตัวอย่างเปรียบเทียบ)",
        target_occupation_cluster: "Accounting & Finance",
        created_at: "2026-11-18T11:00:00Z",
        skills: [
          { curriculum_id: 2, skill_key: 1, course_name: "โปรแกรมสำนักงานเพื่อการบัญชี" },
          { curriculum_id: 2, skill_key: 42, course_name: "การบัญชีชั้นกลาง" },
          { curriculum_id: 2, skill_key: 43, course_name: "การบัญชีภาษีอากร" },
          { curriculum_id: 2, skill_key: 104, course_name: "การสื่อสารทางธุรกิจ" },
        ],
      },
    ],
  },
  admin: {
    key: "admin",
    labelTh: "Admin",
    labelEn: "Admin",
    descriptionTh: "ตรวจสอบ Pipeline, Data Quality, คิว Taxonomy Alias (pg_trgm) และ Sources",
    descriptionEn: "Monitor Scrape Pipeline, Data Quality, pg_trgm Taxonomy Queue & Sources",
    role: "admin",
    defaultRedirect: "/admin/pipeline",
    session: {
      user_id: "00000000-0000-4000-8000-000000000104",
      email: "demo.admin@example.com",
      role: "admin",
      display_name: "ผู้ดูแลระบบ (Demo Admin)",
      province_th: "สงขลา",
      target_occupation_cluster: null,
      preferred_language: "th",
      is_demo: true,
      persona: "admin",
    },
    initialSkills: [],
    initialCurricula: [],
  },
};

export function getDemoCredentialsFromEnv(persona: DemoPersonaKey): {
  email: string;
  password: string;
} | null {
  const map: Record<DemoPersonaKey, [string, string]> = {
    student_data: ["DEMO_STUDENT_DATA_EMAIL", "DEMO_STUDENT_DATA_PASSWORD"],
    student_acc: ["DEMO_STUDENT_ACC_EMAIL", "DEMO_STUDENT_ACC_PASSWORD"],
    institution: ["DEMO_INSTITUTION_EMAIL", "DEMO_INSTITUTION_PASSWORD"],
    admin: ["DEMO_ADMIN_EMAIL", "DEMO_ADMIN_PASSWORD"],
  };
  const [eKey, pKey] = map[persona];
  const email = process.env[eKey]?.trim();
  const password = process.env[pKey]?.trim();
  if (!email || !password || password === "change-me") return null;
  return { email, password };
}
