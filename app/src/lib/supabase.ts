import AsyncStorage from "@react-native-async-storage/async-storage";
import { createClient } from "@supabase/supabase-js";
import { AppState } from "react-native";

import { env } from "@/lib/env";

// With a broken build setting the app only shows the "not set up" screen and never signs in, but
// this module is still loaded, and createClient throws on an empty value. The stand-ins keep the
// load from crashing; they are never contacted.
export const supabase = createClient(
  env.supabaseUrl || "https://not-configured.invalid",
  env.supabaseKey || "not-configured",
  {
    auth: {
      storage: AsyncStorage, // app-private storage on Android
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: false,
    },
  },
);

// Refresh the session only while the app is in the foreground.
AppState.addEventListener("change", (state) => {
  if (state === "active") {
    supabase.auth.startAutoRefresh();
  } else {
    supabase.auth.stopAutoRefresh();
  }
});
