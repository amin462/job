export const MIN_PUBLIC_N = 5;

export const FORBIDDEN_POSTING_TEXT_KEYS = [
  "description",
  "qualifications",
  "telephone",
  "email",
  "contactPoint",
  "applicationContact",
  "faxNumber",
  "contact",
] as const;

export const FORBIDDEN_ML_FAIRNESS_KEYS = ["gender", "age", "company_name"] as const;

export const FORBIDDEN_SOURCES = ["jobtopgun", "jobsdb", "indeed"] as const;

export const ALLOWED_SOURCES = [
  {
    name: "JobThai",
    role: "Primary Source",
    robotsStatus: "Allow: /",
    tosSummary: "ห้ามทำซ้ำ/เผยแพร่ข้อความประกาศซ้ำ เว้นแต่ได้รับอนุญาต — แสดงเฉพาะสถิติรวม (n ≥ 5) และลิงก์ต้นฉบับ",
    politeRate: "1 request / ≥ 5 วินาที (+ jitter), หยุดทันทีเมื่อเจอ 403 / 429 / CAPTCHA",
    permissionStatus: "ร่างหนังสือขออนุญาตแล้ว (รอส่งจริง T0.3)",
  },
  {
    name: "JobBKK",
    role: "Secondary Source (Could)",
    robotsStatus: "อนุญาตหน้าประกาศ (JS listing)",
    tosSummary: "ห้ามใช้เชิงพาณิชย์ — ใช้เพื่อการศึกษาเท่านั้น กรณี JobThai ไม่เพียงพอ",
    politeRate: "1 request / ≥ 5 วินาที, หยุดทันทีเมื่อถูกจำกัดสิทธิ์",
    permissionStatus: "สำรอง (Phase 8 T8.6)",
  },
] as const;

export function isLowData(n: number | null | undefined): boolean {
  return (n ?? 0) < MIN_PUBLIC_N;
}

export function suppressIfLowN<T>(n: number | null | undefined, value: T): T | null {
  if (isLowData(n)) return null;
  return value;
}

export function findForbiddenKeysDeep(
  input: unknown,
  forbiddenKeys: readonly string[] = FORBIDDEN_POSTING_TEXT_KEYS,
  path = ""
): string[] {
  const hits: string[] = [];
  if (Array.isArray(input)) {
    input.forEach((item, idx) => {
      hits.push(...findForbiddenKeysDeep(item, forbiddenKeys, `${path}[${idx}]`));
    });
    return hits;
  }
  if (input && typeof input === "object") {
    for (const [key, val] of Object.entries(input as Record<string, unknown>)) {
      const nextPath = path ? `${path}.${key}` : key;
      if (forbiddenKeys.includes(key)) {
        hits.push(nextPath);
      }
      hits.push(...findForbiddenKeysDeep(val, forbiddenKeys, nextPath));
    }
  }
  return hits;
}

export function isSafeExternalJobUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return false;
    const host = parsed.hostname.toLowerCase();
    return !FORBIDDEN_SOURCES.some((src) => host.includes(src));
  } catch {
    return false;
  }
}

export function checkProfileRoleUpdateAllowed(
  actorRole: string,
  requestedRole: string
): { allowed: boolean; reason?: string } {
  if (actorRole === "admin") {
    return { allowed: true };
  }
  if (requestedRole === "admin") {
    return {
      allowed: false,
      reason: "RLS policy blocks non-admin users from setting role = 'admin'",
    };
  }
  if (requestedRole === "student" || requestedRole === "institution") {
    return { allowed: true };
  }
  return { allowed: false, reason: "Invalid role" };
}

export function checkRouteAccess(
  pathname: string,
  role: string | null | undefined
): { allowed: boolean; redirectTo?: string } {
  const effectiveRole = role || "visitor";

  if (pathname.startsWith("/admin")) {
    if (effectiveRole !== "admin") {
      return {
        allowed: false,
        redirectTo: effectiveRole === "visitor" ? `/login?next=${encodeURIComponent(pathname)}` : "/?error=forbidden",
      };
    }
    return { allowed: true };
  }

  if (pathname.startsWith("/me")) {
    if (effectiveRole === "visitor") {
      return { allowed: false, redirectTo: `/login?next=${encodeURIComponent(pathname)}` };
    }
    if (effectiveRole !== "student" && effectiveRole !== "admin") {
      return { allowed: false, redirectTo: "/?error=forbidden" };
    }
    return { allowed: true };
  }

  if (pathname.startsWith("/institution")) {
    if (effectiveRole === "visitor") {
      return { allowed: false, redirectTo: `/login?next=${encodeURIComponent(pathname)}` };
    }
    if (effectiveRole !== "institution" && effectiveRole !== "admin") {
      return { allowed: false, redirectTo: "/?error=forbidden" };
    }
    return { allowed: true };
  }

  if (pathname.startsWith("/settings") || pathname.startsWith("/onboarding")) {
    if (effectiveRole === "visitor") {
      return { allowed: false, redirectTo: `/login?next=${encodeURIComponent(pathname)}` };
    }
    return { allowed: true };
  }

  return { allowed: true };
}
