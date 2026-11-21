export function isSupabaseConfigured(): boolean {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim();
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim();
  if (!url || !anonKey) return false;
  if (url.includes("your-project-id") || anonKey.includes("your-anon-key")) return false;
  return url.startsWith("https://") || url.startsWith("http://");
}

export function getSupabaseEnv() {
  return {
    url: process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() || "",
    anonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim() || "",
    serviceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY?.trim() || "",
  };
}

export function isServiceRoleConfigured(): boolean {
  const { serviceRoleKey } = getSupabaseEnv();
  return Boolean(
    isSupabaseConfigured() &&
      serviceRoleKey &&
      !serviceRoleKey.includes("your-service-role-key")
  );
}
