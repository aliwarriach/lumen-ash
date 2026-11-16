import { checkEnv } from "@/lib/env-check";

// EXPO_PUBLIC_* values are inlined at build time, so each must be read by its full literal name.
const checked = checkEnv(
  {
    EXPO_PUBLIC_SUPABASE_URL: process.env.EXPO_PUBLIC_SUPABASE_URL,
    EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY: process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    EXPO_PUBLIC_API_URL: process.env.EXPO_PUBLIC_API_URL,
  },
  !__DEV__,
);

export const env = checked.env;

/** What is wrong with this build's settings. Empty when all is well. The root layout shows these
 * instead of the app (see app/_layout.tsx), so nothing below it runs with a broken setting. */
export const envProblems: readonly string[] = checked.problems;
