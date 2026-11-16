import { createAsyncStoragePersister } from "@tanstack/query-async-storage-persister";
import { QueryClient } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { ShareIntentProvider } from "expo-share-intent";
import * as SplashScreen from "expo-splash-screen";
import { useEffect } from "react";
import { ActivityIndicator } from "react-native";

import { shouldRetry } from "@/api/errors";
import { AuthProvider, useAuth } from "@/auth/AuthProvider";
import { clearTaskReminders } from "@/features/capture/reminders";
import { clearTicks } from "@/features/dashboard/ticks";
import { clearReminder } from "@/features/reminders/reminder";
import { clearOutbox } from "@/features/review/outbox";
import { envProblems } from "@/lib/env";
import { supabase } from "@/lib/supabase";
import { Centered } from "@/ui/components";
import { ConfigProblemScreen } from "@/ui/ErrorScreen";
import { APP_FONTS } from "@/ui/fonts";
import { AppThemeProvider } from "@/ui/ThemeProvider";

// Keep the splash screen up until the app font has loaded, so text never jumps from one font to
// another on the first screen.
void SplashScreen.preventAutoHideAsync().catch(() => {});

// If any screen crashes, show a way out instead of a blank page.
export { AppErrorBoundary as ErrorBoundary } from "@/ui/ErrorScreen";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: shouldRetry, staleTime: 30_000 },
  },
});

// The review queue and the Today screen are kept on the phone: enough to review and see the
// plan offline, nothing more.
const persister = createAsyncStoragePersister({ storage: AsyncStorage, key: "query-cache:v1" });
const persistOptions = {
  persister,
  maxAge: 24 * 60 * 60_000,
  // Change this whenever a kept response changes shape (v3: the dashboard gained on_track.week).
  // Data saved under another buster is thrown away on start, so an old saved plan can never be
  // drawn by a screen that expects the new fields, which would crash before it fetches a new one.
  buster: "v3",
  dehydrateOptions: {
    shouldDehydrateQuery: (q: { queryKey: readonly unknown[]; state: { status: string } }) =>
      (q.queryKey[0] === "reviews" || q.queryKey[0] === "dashboard") &&
      q.state.status === "success",
  },
};

/** Study data stays private: signing out removes everything kept on the phone. */
function useClearDataOnSignOut() {
  useEffect(() => {
    const { data } = supabase.auth.onAuthStateChange((event) => {
      if (event === "SIGNED_OUT") {
        queryClient.clear();
        void persister.removeClient();
        void clearOutbox();
        void clearTicks();
        void clearReminder();
        void clearTaskReminders();
      }
    });
    return () => data.subscription.unsubscribe();
  }, []);
}

function RootNavigator() {
  const { session, loading } = useAuth();
  useClearDataOnSignOut();

  if (loading) {
    return (
      <Centered>
        <ActivityIndicator />
      </Centered>
    );
  }

  const signedIn = session !== null;
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Protected guard={signedIn}>
        <Stack.Screen name="(app)" />
      </Stack.Protected>
      <Stack.Protected guard={!signedIn}>
        <Stack.Screen name="sign-in" />
        <Stack.Screen name="sign-up" />
        <Stack.Screen name="forgot-password" />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts(APP_FONTS);
  // If the font can't load, carry on in the phone's own font rather than never opening.
  const fontsReady = fontsLoaded || fontError !== null;
  useEffect(() => {
    if (fontsReady) SplashScreen.hide();
  }, [fontsReady]);
  if (!fontsReady) return null;

  // A build made without its settings can't sign in or reach the server. Say so, and say which.
  if (envProblems.length > 0) {
    return (
      <AppThemeProvider>
        <ConfigProblemScreen problems={envProblems} />
      </AppThemeProvider>
    );
  }
  return (
    // The share-intent provider goes outermost, as its docs ask: a message shared from another app
    // must be caught even before sign-in finishes, and is handled once the learner is in.
    <ShareIntentProvider>
      <AppThemeProvider>
        <PersistQueryClientProvider client={queryClient} persistOptions={persistOptions}>
          <AuthProvider>
            <RootNavigator />
          </AuthProvider>
        </PersistQueryClientProvider>
      </AppThemeProvider>
    </ShareIntentProvider>
  );
}
