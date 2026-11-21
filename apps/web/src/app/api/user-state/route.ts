import { NextResponse, type NextRequest } from "next/server";
import { getCurrentSession, getDemoStore } from "@/lib/auth";
import { checkProfileRoleUpdateAllowed } from "@/lib/compliance";
import { getPublicDimSkills } from "@/lib/data";
import { isSupabaseConfigured } from "@/lib/supabase/config";
import {
  createSupabaseServerClient,
  createSupabaseServiceClient,
} from "@/lib/supabase/server";
import { DEMO_SESSION_COOKIE } from "@/lib/supabase/middleware";
import type { CurriculumItem, UserSession } from "@/types/marts";

export async function POST(request: NextRequest) {
  const session = await getCurrentSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const action = String(body.action || "");
  const store = getDemoStore();

  // 1. Profile / Onboarding Update (strictly blocks self-elevation to admin)
  if (action === "update_profile") {
    const requestedRole = String(body.role || session.role);
    const guard = checkProfileRoleUpdateAllowed(session.role, requestedRole);
    if (!guard.allowed) {
      return NextResponse.json(
        { error: guard.reason || "Forbidden role update" },
        { status: 403 }
      );
    }

    const updated: UserSession = {
      ...session,
      role: requestedRole as UserSession["role"],
      display_name: String(body.display_name || session.display_name).slice(0, 80),
      province_th: body.province_th ? String(body.province_th) : session.province_th,
      target_occupation_cluster: body.target_occupation_cluster
        ? String(body.target_occupation_cluster)
        : session.target_occupation_cluster,
    };

    if (!session.is_demo && isSupabaseConfigured()) {
      const supabase = await createSupabaseServerClient();
      if (supabase) {
        const { error } = await supabase
          .from("app_profile")
          .update({
            role: updated.role,
            display_name: updated.display_name,
            province_th: updated.province_th,
            target_occupation_cluster: updated.target_occupation_cluster,
          })
          .eq("user_id", session.user_id);
        if (error) {
          return NextResponse.json({ error: error.message }, { status: 403 });
        }
        return NextResponse.json({ ok: true, session: updated });
      }
    }

    store.profiles[session.user_id] = updated;
    const res = NextResponse.json({ ok: true, session: updated });
    res.cookies.set(
      DEMO_SESSION_COOKIE,
      encodeURIComponent(JSON.stringify(updated)),
      { httpOnly: true, sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 7 }
    );
    return res;
  }

  // 2. User Skills CRUD
  if (action === "upsert_skill") {
    const skillKey = Number(body.skill_key);
    const level = Math.min(3, Math.max(1, Number(body.level || 2))) as 1 | 2 | 3;
    const dimSkills = await getPublicDimSkills();
    const meta = dimSkills.find((s) => s.skill_key === skillKey);
    if (!meta) {
      return NextResponse.json({ error: "Skill not found" }, { status: 404 });
    }

    if (!session.is_demo && isSupabaseConfigured()) {
      const supabase = await createSupabaseServerClient();
      if (supabase) {
        const { error } = await supabase
          .from("app_user_skill")
          .upsert({ user_id: session.user_id, skill_key: skillKey, level });
        if (error) {
          return NextResponse.json({ error: error.message }, { status: 400 });
        }
        return NextResponse.json({ ok: true });
      }
    }

    const list = store.skillsByUser[session.user_id] ?? [];
    const idx = list.findIndex((s) => s.skill_key === skillKey);
    const item = {
      skill_key: meta.skill_key,
      skill_canonical: meta.skill_canonical,
      skill_slug: meta.skill_slug,
      skill_name_th: meta.skill_name_th,
      skill_type: meta.skill_type,
      skill_group: meta.skill_group,
      level,
    };
    if (idx >= 0) list[idx] = item;
    else list.push(item);
    store.skillsByUser[session.user_id] = list;
    return NextResponse.json({ ok: true, skills: list });
  }

  if (action === "remove_skill") {
    const skillKey = Number(body.skill_key);
    if (!session.is_demo && isSupabaseConfigured()) {
      const supabase = await createSupabaseServerClient();
      if (supabase) {
        await supabase
          .from("app_user_skill")
          .delete()
          .eq("user_id", session.user_id)
          .eq("skill_key", skillKey);
        return NextResponse.json({ ok: true });
      }
    }
    store.skillsByUser[session.user_id] = (
      store.skillsByUser[session.user_id] ?? []
    ).filter((s) => s.skill_key !== skillKey);
    return NextResponse.json({
      ok: true,
      skills: store.skillsByUser[session.user_id],
    });
  }

  if (action === "clear_skills") {
    if (!session.is_demo && isSupabaseConfigured()) {
      const supabase = await createSupabaseServerClient();
      if (supabase) {
        await supabase
          .from("app_user_skill")
          .delete()
          .eq("user_id", session.user_id);
        return NextResponse.json({ ok: true });
      }
    }
    store.skillsByUser[session.user_id] = [];
    return NextResponse.json({ ok: true, skills: [] });
  }

  // 3. Curricula CRUD
  if (action === "create_curriculum") {
    const name = String(body.name || "").trim();
    const target = String(body.target_occupation_cluster || "Data & Analytics").trim();
    if (!name) {
      return NextResponse.json({ error: "Name required" }, { status: 400 });
    }

    if (!session.is_demo && isSupabaseConfigured()) {
      const supabase = await createSupabaseServerClient();
      if (supabase) {
        const { data, error } = await supabase
          .from("app_curriculum")
          .insert({
            owner_id: session.user_id,
            name,
            target_occupation_cluster: target,
          })
          .select("*")
          .single();
        if (error) {
          return NextResponse.json({ error: error.message }, { status: 400 });
        }
        return NextResponse.json({ ok: true, curriculum: { ...data, skills: [] } });
      }
    }

    const id = store.nextCurriculumId++;
    const created: CurriculumItem = {
      curriculum_id: id,
      owner_id: session.user_id,
      name,
      target_occupation_cluster: target,
      created_at: new Date().toISOString(),
      skills: [],
    };
    const curList = store.curriculaByUser[session.user_id] ?? [];
    curList.push(created);
    store.curriculaByUser[session.user_id] = curList;
    return NextResponse.json({ ok: true, curriculum: created });
  }

  if (action === "delete_curriculum") {
    const cid = Number(body.curriculum_id);
    if (!session.is_demo && isSupabaseConfigured()) {
      const supabase = await createSupabaseServerClient();
      if (supabase) {
        await supabase
          .from("app_curriculum")
          .delete()
          .eq("curriculum_id", cid)
          .eq("owner_id", session.user_id);
        return NextResponse.json({ ok: true });
      }
    }
    store.curriculaByUser[session.user_id] = (
      store.curriculaByUser[session.user_id] ?? []
    ).filter((c) => c.curriculum_id !== cid);
    return NextResponse.json({ ok: true });
  }

  if (action === "add_curriculum_skill") {
    const cid = Number(body.curriculum_id);
    const skillKey = Number(body.skill_key);
    const courseName = String(body.course_name || "รายวิชาทั่วไป").trim();
    if (!session.is_demo && isSupabaseConfigured()) {
      const supabase = await createSupabaseServerClient();
      if (supabase) {
        const { error } = await supabase.from("app_curriculum_skill").upsert({
          curriculum_id: cid,
          skill_key: skillKey,
          course_name: courseName,
        });
        if (error) {
          return NextResponse.json({ error: error.message }, { status: 400 });
        }
        return NextResponse.json({ ok: true });
      }
    }
    const list = store.curriculaByUser[session.user_id] ?? [];
    const targetCur = list.find((c) => c.curriculum_id === cid);
    if (!targetCur) {
      return NextResponse.json({ error: "Curriculum not found" }, { status: 404 });
    }
    if (
      !targetCur.skills.some(
        (s) => s.skill_key === skillKey && s.course_name === courseName
      )
    ) {
      targetCur.skills.push({
        curriculum_id: cid,
        skill_key: skillKey,
        course_name: courseName,
      });
    }
    return NextResponse.json({ ok: true, curriculum: targetCur });
  }

  if (action === "remove_curriculum_skill") {
    const cid = Number(body.curriculum_id);
    const skillKey = Number(body.skill_key);
    const courseName = String(body.course_name || "");
    if (!session.is_demo && isSupabaseConfigured()) {
      const supabase = await createSupabaseServerClient();
      if (supabase) {
        await supabase
          .from("app_curriculum_skill")
          .delete()
          .eq("curriculum_id", cid)
          .eq("skill_key", skillKey)
          .eq("course_name", courseName);
        return NextResponse.json({ ok: true });
      }
    }
    const list = store.curriculaByUser[session.user_id] ?? [];
    const targetCur = list.find((c) => c.curriculum_id === cid);
    if (targetCur) {
      targetCur.skills = targetCur.skills.filter(
        (s) => !(s.skill_key === skillKey && s.course_name === courseName)
      );
    }
    return NextResponse.json({ ok: true });
  }

  if (action === "import_curriculum_csv") {
    const cid = Number(body.curriculum_id);
    const rows = Array.isArray(body.rows)
      ? (body.rows as Array<{ course: string; skill: string }>)
      : [];

    const dimSkills = await getPublicDimSkills();
    const matchedEntries: Array<{ course_name: string; skill_key: number }> = [];
    for (const r of rows) {
      const q = String(r.skill || "").trim().toLowerCase();
      const courseName = String(r.course || "").trim() || "รายวิชาที่นำเข้า";
      const found = dimSkills.find(
        (sk) =>
          sk.skill_canonical.toLowerCase() === q ||
          sk.skill_name_th.toLowerCase() === q ||
          sk.aliases.some((a) => a.toLowerCase() === q)
      );
      if (found) {
        matchedEntries.push({ course_name: courseName, skill_key: found.skill_key });
      }
    }

    if (!session.is_demo && isSupabaseConfigured()) {
      const supabase = await createSupabaseServerClient();
      if (supabase && matchedEntries.length > 0) {
        await supabase.from("app_curriculum_skill").upsert(
          matchedEntries.map((m) => ({
            curriculum_id: cid,
            skill_key: m.skill_key,
            course_name: m.course_name,
          }))
        );
      }
      return NextResponse.json({ ok: true, importedCount: matchedEntries.length });
    }

    const list = store.curriculaByUser[session.user_id] ?? [];
    const targetCur = list.find((c) => c.curriculum_id === cid);
    if (!targetCur) {
      return NextResponse.json({ error: "Curriculum not found" }, { status: 404 });
    }
    for (const m of matchedEntries) {
      if (
        !targetCur.skills.some(
          (s) => s.skill_key === m.skill_key && s.course_name === m.course_name
        )
      ) {
        targetCur.skills.push({
          curriculum_id: cid,
          skill_key: m.skill_key,
          course_name: m.course_name,
        });
      }
    }
    return NextResponse.json({ ok: true, importedCount: matchedEntries.length });
  }

  // 4. Admin Taxonomy Review (Admin ONLY)
  if (action === "admin_review_alias") {
    if (session.role !== "admin") {
      return NextResponse.json(
        { error: "Forbidden: admin role required" },
        { status: 403 }
      );
    }
    const suggestionId = Number(body.suggestion_id);
    const reviewAction = String(body.review_action || "");
    const targetSkillKey = body.target_skill_key
      ? Number(body.target_skill_key)
      : undefined;

    if (!session.is_demo && isSupabaseConfigured()) {
      const supabase = await createSupabaseServerClient();
      if (supabase) {
        const { data, error } = await supabase.rpc("admin_review_alias", {
          p_suggestion_id: suggestionId,
          p_action: reviewAction,
          p_target_skill_key: targetSkillKey ?? null,
        });
        if (error) {
          return NextResponse.json({ error: error.message }, { status: 400 });
        }
        return NextResponse.json({ ok: true, data });
      }
    }

    store.aliasOverrides[suggestionId] = {
      status: reviewAction === "reject" ? "rejected" : "approved",
      skill_key: targetSkillKey,
    };
    return NextResponse.json({ ok: true });
  }

  // 5. Account / Demo Data Reset (PDPA delete own data)
  if (action === "delete_account") {
    if (!session.is_demo && isSupabaseConfigured()) {
      const supabase = await createSupabaseServerClient();
      if (supabase) {
        await supabase.from("app_user_skill").delete().eq("user_id", session.user_id);
        await supabase.from("app_curriculum").delete().eq("owner_id", session.user_id);
        await supabase.from("app_profile").delete().eq("user_id", session.user_id);

        const demoEmails = new Set(
          [
            process.env.DEMO_STUDENT_DATA_EMAIL,
            process.env.DEMO_STUDENT_ACC_EMAIL,
            process.env.DEMO_INSTITUTION_EMAIL,
            process.env.DEMO_ADMIN_EMAIL,
          ]
            .map((e) => (e || "").trim().toLowerCase())
            .filter(Boolean)
        );
        const sessionEmail = (session.email || "").trim().toLowerCase();
        if (!sessionEmail || !demoEmails.has(sessionEmail)) {
          const service = await createSupabaseServiceClient();
          if (service) {
            await service.auth.admin.deleteUser(session.user_id);
          }
        }
        await supabase.auth.signOut();
      }
    }

    delete store.skillsByUser[session.user_id];
    delete store.curriculaByUser[session.user_id];
    delete store.profiles[session.user_id];

    const res = NextResponse.json({ ok: true });
    res.cookies.delete(DEMO_SESSION_COOKIE);
    return res;
  }

  return NextResponse.json({ error: "Unknown action" }, { status: 400 });
}
