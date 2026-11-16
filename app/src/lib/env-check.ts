// Checks the three build settings. Pure (no React Native imports) so `npm test` can run it.
//
// A build with a missing or wrong value used to crash while loading, which in a release build is
// a blank screen with no clue. Now the app opens on a screen that names the problem.

export type RawEnv = {
  EXPO_PUBLIC_SUPABASE_URL?: string;
  EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY?: string;
  EXPO_PUBLIC_API_URL?: string;
};

export type Env = { supabaseUrl: string; supabaseKey: string; apiUrl: string };

// Names that mean a secret was put where the whole world can read it.
const SECRET_LOOKING = /^(sb_secret_|gsk_|AIza)|service_role/;

/**
 * The settings to use and what is wrong with them, if anything. `release` is true for an
 * installed build (not the development server): Android then refuses plain http.
 */
export function checkEnv(raw: RawEnv, release: boolean): { env: Env; problems: string[] } {
  const supabaseUrl = (raw.EXPO_PUBLIC_SUPABASE_URL ?? "").trim().replace(/\/+$/, "");
  const supabaseKey = (raw.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "").trim();
  const apiUrl = (raw.EXPO_PUBLIC_API_URL ?? "").trim().replace(/\/+$/, "");
  const problems: string[] = [];

  if (!supabaseUrl) problems.push("EXPO_PUBLIC_SUPABASE_URL is missing.");
  else if (!/^https:\/\/[^\s/]+$/.test(supabaseUrl) && !isLocal(supabaseUrl)) {
    problems.push("EXPO_PUBLIC_SUPABASE_URL must look like https://your-project.supabase.co");
  }

  if (!supabaseKey) problems.push("EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY is missing.");
  else if (SECRET_LOOKING.test(supabaseKey) || isServiceRoleJwt(supabaseKey)) {
    problems.push(
      "EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY holds a secret key. Use the publishable (anon) key, and replace the secret one in Supabase: it has been exposed.",
    );
  }

  if (!apiUrl) problems.push("EXPO_PUBLIC_API_URL is missing.");
  else if (!/^https?:\/\/[^\s/]+/.test(apiUrl)) {
    problems.push("EXPO_PUBLIC_API_URL must start with https:// (or http:// while developing).");
  } else if (release && !apiUrl.startsWith("https://")) {
    problems.push(
      "EXPO_PUBLIC_API_URL must start with https:// in an installed build: Android blocks plain http.",
    );
  }

  return { env: { supabaseUrl, supabaseKey, apiUrl }, problems };
}

function isLocal(url: string): boolean {
  return /^http:\/\/(localhost|127\.0\.0\.1|10\.|192\.168\.)/.test(url);
}

/** Supabase's old-style keys are JWTs whose payload names the role. */
function isServiceRoleJwt(key: string): boolean {
  const payload = key.split(".")[1];
  if (!payload) return false;
  try {
    return atob(payload.replace(/-/g, "+").replace(/_/g, "/")).includes("service_role");
  } catch {
    return false;
  }
}
