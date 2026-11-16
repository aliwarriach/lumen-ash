import AsyncStorage from "@react-native-async-storage/async-storage";
import { DarkTheme, DefaultTheme, ThemeProvider as NavigationTheme } from "expo-router";
import { StatusBar } from "expo-status-bar";
import * as SystemUI from "expo-system-ui";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useColorScheme } from "react-native";

import { dark, light, ThemeContext, type Palette } from "@/ui/theme";

/** "system" follows the phone's setting; the drawer's Dark mode switch picks light or dark. */
export type ThemePreference = "system" | "light" | "dark";

const KEY = "theme-preference:v1";

type PreferenceValue = {
  preference: ThemePreference;
  setPreference: (p: ThemePreference) => void;
};

const PreferenceContext = createContext<PreferenceValue>({
  preference: "system",
  setPreference: () => {},
});

/** The learner's light/dark choice, for the switch in the drawer. */
export function useThemePreference(): PreferenceValue {
  return useContext(PreferenceContext);
}

export function paletteFor(preference: ThemePreference, system: string | null | undefined): Palette {
  const scheme = preference === "system" ? system : preference;
  return scheme === "dark" ? dark : light;
}

/**
 * Supplies the active palette to every screen, the matching colors to the navigators (headers,
 * tab bar, screen backgrounds) and the matching status bar icons.
 */
export function AppThemeProvider({ children }: { children: ReactNode }) {
  const system = useColorScheme();
  const [preference, setPreferenceState] = useState<ThemePreference>("system");

  useEffect(() => {
    AsyncStorage.getItem(KEY)
      .then((saved) => {
        if (saved === "light" || saved === "dark") setPreferenceState(saved);
      })
      .catch(() => {}); // Not saved yet, or storage unavailable: follow the phone.
  }, []);

  const value = useMemo<PreferenceValue>(
    () => ({
      preference,
      setPreference: (p) => {
        setPreferenceState(p);
        void (p === "system" ? AsyncStorage.removeItem(KEY) : AsyncStorage.setItem(KEY, p)).catch(
          () => {},
        );
      },
    }),
    [preference],
  );

  const palette = paletteFor(preference, system);

  // The window behind the screens: without this, a screen change flashes white in dark mode.
  useEffect(() => {
    void SystemUI.setBackgroundColorAsync(palette.background).catch(() => {});
  }, [palette.background]);
  const navigationTheme = useMemo(() => {
    const base = palette.scheme === "dark" ? DarkTheme : DefaultTheme;
    return {
      ...base,
      colors: {
        ...base.colors,
        primary: palette.primary,
        background: palette.background,
        card: palette.background,
        text: palette.text,
        border: palette.divider,
        notification: palette.primary,
      },
    };
  }, [palette]);

  return (
    <PreferenceContext.Provider value={value}>
      <ThemeContext.Provider value={palette}>
        <NavigationTheme value={navigationTheme}>
          <StatusBar style={palette.scheme === "dark" ? "light" : "dark"} />
          {children}
        </NavigationTheme>
      </ThemeContext.Provider>
    </PreferenceContext.Provider>
  );
}
