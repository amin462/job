import { NextResponse, type NextRequest } from "next/server";
import { DEMO_PERSONAS, getDemoCredentialsFromEnv } from "@/lib/demo-personas";
import { seedPersonaIntoStore } from "@/lib/auth";
import { isSupabaseConfigured } from "@/lib/supabase/config";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { DEMO_SESSION_COOKIE } from "@/lib/supabase/middleware";
import type { DemoPersonaKey } from "@/types/marts";

export async function POST(request: NextRequest) {
  let body: { persona?: string };
  try {
    body = (await request.json()) as { persona?: string };
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const personaKey = body.persona as DemoPersonaKey;
  if (!personaKey || !(personaKey in DEMO_PERSONAS)) {
    return NextResponse.json({ error: "Unknown demo persona" }, { status: 400 });
  }

  const spec = DEMO_PERSONAS[personaKey];

  // Try real Supabase Auth if demo env credentials are configured
  const envCreds = getDemoCredentialsFromEnv(personaKey);
  if (isSupabaseConfigured() && envCreds) {
    try {
      const supabase = await createSupabaseServerClient();
      if (supabase) {
        const { data, error } = await supabase.auth.signInWithPassword({
          email: envCreds.email,
          password: envCreds.password,
        });
        if (!error && data.user) {
          const res = NextResponse.json({
            ok: true,
            mode: "supabase",
            redirectTo: spec.defaultRedirect,
            session: {
              ...spec.session,
              user_id: data.user.id,
              is_demo: true,
            },
          });
          res.cookies.delete(DEMO_SESSION_COOKIE);
          return res;
        }
      }
    } catch {
      // fall back to offline demo cookie session
    }
  }

  // Offline demo cookie session
  const session = seedPersonaIntoStore(personaKey);
  const res = NextResponse.json({
    ok: true,
    mode: "offline-demo",
    redirectTo: spec.defaultRedirect,
    session,
  });

  res.cookies.set(
    DEMO_SESSION_COOKIE,
    encodeURIComponent(JSON.stringify(session)),
    {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 7,
    }
  );
  return res;
}

export async function DELETE() {
  if (isSupabaseConfigured()) {
    try {
      const supabase = await createSupabaseServerClient();
      await supabase?.auth.signOut();
    } catch {
      // ignore
    }
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.delete(DEMO_SESSION_COOKIE);
  return res;
}
