// Run with `npm test`. The build-settings check that decides between the app and the
// "this copy isn't set up" screen.
import assert from "node:assert/strict";
import { test } from "node:test";

import { checkEnv } from "../src/lib/env-check";

const good = {
  EXPO_PUBLIC_SUPABASE_URL: "https://abcd1234.supabase.co/",
  EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_abc123",
  EXPO_PUBLIC_API_URL: "https://lumen-backend.onrender.com/",
};

test("good settings pass, with trailing slashes removed", () => {
  const { env, problems } = checkEnv(good, true);
  assert.deepEqual(problems, []);
  assert.deepEqual(env, {
    supabaseUrl: "https://abcd1234.supabase.co",
    supabaseKey: "sb_publishable_abc123",
    apiUrl: "https://lumen-backend.onrender.com",
  });
});

test("every missing value is named, and nothing throws", () => {
  const { problems } = checkEnv({}, true);
  assert.equal(problems.length, 3);
  for (const name of Object.keys(good)) {
    assert.ok(problems.some((p) => p.startsWith(`${name} is missing`)), name);
  }
});

test("a LAN address over http is fine while developing but refused in an installed build", () => {
  const lan = { ...good, EXPO_PUBLIC_API_URL: "http://192.168.1.20:8000" };
  assert.deepEqual(checkEnv(lan, false).problems, []);
  const [problem, ...rest] = checkEnv(lan, true).problems;
  assert.match(problem, /EXPO_PUBLIC_API_URL must start with https:\/\/ in an installed build/);
  assert.deepEqual(rest, []);
});

test("an address that is not a URL is refused", () => {
  const { problems } = checkEnv({ ...good, EXPO_PUBLIC_API_URL: "lumen-backend.onrender.com" }, false);
  assert.match(problems[0], /EXPO_PUBLIC_API_URL must start with https:\/\//);
  const bad = checkEnv({ ...good, EXPO_PUBLIC_SUPABASE_URL: "abcd1234.supabase.co" }, false);
  assert.match(bad.problems[0], /EXPO_PUBLIC_SUPABASE_URL must look like/);
});

test("a secret key in the app's settings is caught: the APK can be unpacked by anyone", () => {
  const serviceRole =
    "eyJhbGciOiJIUzI1NiJ9." + btoa(JSON.stringify({ role: "service_role" })) + ".signature";
  for (const key of ["sb_secret_abc", "gsk_abcdef", "AIzaSyExample", serviceRole]) {
    const { problems } = checkEnv({ ...good, EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY: key }, true);
    assert.match(problems[0] ?? "", /holds a secret key/, key.slice(0, 10));
  }
  const anon = "eyJhbGciOiJIUzI1NiJ9." + btoa(JSON.stringify({ role: "anon" })) + ".signature";
  assert.deepEqual(checkEnv({ ...good, EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY: anon }, true).problems, []);
});
