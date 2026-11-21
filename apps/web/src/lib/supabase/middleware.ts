import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { checkRouteAccess } from "@/lib/compliance";
import { getSupabaseEnv, isSupabaseConfigured } from "./config";

export const DEMO_SESSION_COOKIE = "southbi_demo_session";

function parseDemoRole(request: NextRequest): string | null {
  const raw = request.cookies.get(DEMO_SESSION_COOKIE)?.value;
  if (!raw) return null;
  try {
    const parsed = JSON.parse(decodeURIComponent(raw)) as { role?: string };
    if (
      parsed.role === "student" ||
      parsed.role === "institution" ||
      parsed.role === "admin"
    ) {
      return parsed.role;
    }
    return null;
  } catch {
    return null;
  }
}

export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({
    request: { headers: request.headers },
  });

  const pathname = request.nextUrl.pathname;
  let effectiveRole: string | null = parseDemoRole(request);

  if (isSupabaseConfigured()) {
    const { url, anonKey } = getSupabaseEnv();
    const supabase = createServerClient(url, anonKey, {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({
            request: { headers: request.headers },
          });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    });

    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (user) {
      const { data: profile } = await supabase
        .from("app_profile")
        .select("role")
        .eq("user_id", user.id)
        .maybeSingle();
      effectiveRole = profile?.role ?? "student";
    }
  }

  const access = checkRouteAccess(pathname, effectiveRole);
  if (!access.allowed && access.redirectTo) {
    const url = request.nextUrl.clone();
    const [targetPath, targetQuery] = access.redirectTo.split("?");
    url.pathname = targetPath;
    url.search = targetQuery ? `?${targetQuery}` : "";
    return NextResponse.redirect(url);
  }

  return response;
}
