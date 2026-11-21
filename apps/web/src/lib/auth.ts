import { cookies } from "next/headers";
import type {
  CurriculumItem,
  DemoPersonaKey,
  PendingAliasRow,
  UserSession,
  UserSkill,
} from "@/types/marts";
import { DEMO_PERSONAS } from "./demo-personas";
import { isSupabaseConfigured } from "./supabase/config";
import { createSupabaseServerClient } from "./supabase/server";
import { DEMO_SESSION_COOKIE } from "./supabase/middleware";

interface DemoStoreState {
  profiles: Record<string, UserSession>;
  skillsByUser: Record<string, UserSkill[]>;
  curriculaByUser: Record<string, CurriculumItem[]>;
  nextCurriculumId: number;
  aliasOverrides: Record<number, { status: "pending" | "approved" | "rejected"; skill_key?: number }>;
  chatLogs: Array<{ chat_id: number; user_id: string | null; page: string; question: string; answered: boolean; created_at: string }>;
}

const g = globalThis as unknown as { __southbiDemoStore?: DemoStoreState };

export function getDemoStore(): DemoStoreState {
  if (!g.__southbiDemoStore) {
    const profiles: Record<string, UserSession> = {};
    const skillsByUser: Record<string, UserSkill[]> = {};
    const curriculaByUser: Record<string, CurriculumItem[]> = {};

    for (const p of Object.values(DEMO_PERSONAS)) {
      profiles[p.session.user_id] = { ...p.session };
      skillsByUser[p.session.user_id] = p.initialSkills.map((s) => ({ ...s }));
      curriculaByUser[p.session.user_id] = p.initialCurricula.map((c) => ({
        ...c,
        skills: c.skills.map((cs) => ({ ...cs })),
      }));
    }

    g.__southbiDemoStore = {
      profiles,
      skillsByUser,
      curriculaByUser,
      nextCurriculumId: 100,
      aliasOverrides: {},
      chatLogs: [
        {
          chat_id: 1,
          user_id: null,
          page: "market",
          question: "ทักษะไหนโตเร็วสุดในช่วงนี้",
          answered: true,
          created_at: "2026-11-18T14:15:00Z",
        },
        {
          chat_id: 2,
          user_id: null,
          page: "salary",
          question: "เพิ่มทักษะไหนคุ้มสุดสำหรับ Data & Analytics",
          answered: true,
          created_at: "2026-11-18T14:40:00Z",
        },
        {
          chat_id: 3,
          user_id: null,
          page: "me-gap",
          question: "ควรเริ่มเรียนอะไรก่อน",
          answered: true,
          created_at: "2026-11-18T15:05:00Z",
        },
      ],
    };
  }
  return g.__southbiDemoStore;
}

export async function getCurrentSession(): Promise<UserSession | null> {
  let demoRaw: string | undefined;
  try {
    const cookieStore = await cookies();
    demoRaw = cookieStore.get(DEMO_SESSION_COOKIE)?.value;
  } catch {
    return null;
  }

  if (isSupabaseConfigured()) {
    const supabase = await createSupabaseServerClient();
    if (supabase) {
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (user) {
        const { data: profile } = await supabase
          .from("app_profile")
          .select("*")
          .eq("user_id", user.id)
          .maybeSingle();
        return {
          user_id: user.id,
          email: user.email || "",
          role: (profile?.role as UserSession["role"]) || "student",
          display_name: profile?.display_name || user.email?.split("@")[0] || "ผู้ใช้",
          province_th: profile?.province_th ?? null,
          target_occupation_cluster: profile?.target_occupation_cluster ?? null,
          preferred_language: profile?.preferred_language === "en" ? "en" : "th",
          is_demo: false,
        };
      }
    }
  }

  if (demoRaw) {
    try {
      const parsed = JSON.parse(decodeURIComponent(demoRaw)) as UserSession;
      if (parsed && parsed.user_id) {
        const store = getDemoStore();
        return store.profiles[parsed.user_id] ?? parsed;
      }
    } catch {
      return null;
    }
  }

  return null;
}

export function getDemoUserSkills(userId: string): UserSkill[] {
  const store = getDemoStore();
  return store.skillsByUser[userId] ?? [];
}

export function getDemoUserCurricula(userId: string): CurriculumItem[] {
  const store = getDemoStore();
  return store.curriculaByUser[userId] ?? [];
}

export function applyDemoAliasOverrides(rows: PendingAliasRow[]): PendingAliasRow[] {
  const store = getDemoStore();
  return rows.map((row) => {
    const ov = store.aliasOverrides[row.suggestion_id];
    if (!ov) return row;
    return {
      ...row,
      status: ov.status,
      suggested_skill_key: ov.skill_key ?? row.suggested_skill_key,
    };
  });
}

export function seedPersonaIntoStore(persona: DemoPersonaKey): UserSession {
  const spec = DEMO_PERSONAS[persona];
  const store = getDemoStore();
  if (!store.profiles[spec.session.user_id]) {
    store.profiles[spec.session.user_id] = { ...spec.session };
    store.skillsByUser[spec.session.user_id] = spec.initialSkills.map((s) => ({ ...s }));
    store.curriculaByUser[spec.session.user_id] = spec.initialCurricula.map((c) => ({
      ...c,
      skills: c.skills.map((cs) => ({ ...cs })),
    }));
  }
  return store.profiles[spec.session.user_id];
}
