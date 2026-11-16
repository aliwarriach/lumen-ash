import { createContext, useContext } from "react";
import { StyleSheet, type ImageStyle, type TextStyle, type ViewStyle } from "react-native";

type NamedStyles = Record<string, ViewStyle | TextStyle | ImageStyle>;

/**
 * Design tokens for the glass restyle (approved 2026-11-13), in a light and a dark palette.
 *
 * Every text pair was checked at 4.5:1 or better, control edges and icons at 3:1, including on a
 * glass card over the brightest backdrop patch. Change a value here only after checking it again.
 *
 * Screens never import a palette directly: they read the active one through `useTheme()` or
 * build their styles with `makeStyles()`, so a switch to dark mode restyles every screen.
 */

/** A text color on its tinted background, e.g. a green "Done" label on a pale green pill. */
export type Accent = { fg: string; bg: string };

/** der / die / das: `fill` + `onFill` once answered, `tint` + `text` on the quiz button. */
export type ArticleColors = { fill: string; onFill: string; tint: string; text: string };

export type Palette = {
  scheme: "light" | "dark";
  // Page and surfaces.
  background: string;
  /** Large blurred color patches drawn behind the glass. */
  backdrop: readonly [string, string, string, string];
  backdropOpacity: number;
  /** A glass card: frosted, with a thin bright edge and a soft shadow. */
  card: string;
  cardBorder: string;
  /** Inputs and plain cards that sit on the page. */
  surface: string;
  /** A section that sits flat on the page, without blur or shadow. */
  flat: string;
  sheet: string;
  nav: string;
  navBorder: string;
  /** The inside of a checkbox, switch or track. */
  well: string;
  divider: string;
  scrim: string;
  shadow: string;
  // Text.
  text: string;
  muted: string;
  /** Edges of controls (inputs, outlined chips, checkboxes): 3:1 against the page. */
  border: string;
  // Brand.
  primary: string;
  onPrimary: string;
  primaryShadow: string;
  primaryContainer: string;
  onPrimaryContainer: string;
  // Status text colors, readable on the page and on cards.
  success: string;
  warning: string;
  danger: string;
  // Accents (text on its container).
  green: Accent;
  amber: Accent;
  orange: Accent;
  pink: Accent;
  teal: Accent;
  /** Bright fills for illustrations only, never for text; `paper` is a book page. */
  illustration: { amber: string; pink: string; teal: string; paper: string };
  /** A ticked checkbox in the plan, and a finished day in the week strip. */
  done: string;
  onDone: string;
  weekDone: string;
  onWeekDone: string;
  /** A wrong answer: text on its background, with a stronger edge. */
  wrong: { fg: string; bg: string; edge: string };
  /** A right answer uses the green accent; kept here so feedback reads as one pair. */
  right: { fg: string; bg: string; edge: string };
  der: ArticleColors;
  die: ArticleColors;
  das: ArticleColors;
  /** Plurals always take "die", so they are shown neutral. */
  plural: string;
  /** Names in the group chat: distinct, readable on the bubbles, none of them red or primary. */
  names: readonly string[];
};

export const light: Palette = {
  scheme: "light",
  background: "#EEF0F8",
  backdrop: ["#A5B4FC", "#99F6E4", "#FDE68A", "#FBCFE8"],
  backdropOpacity: 0.55,
  card: "rgba(255,255,255,0.62)",
  cardBorder: "rgba(255,255,255,0.85)",
  surface: "rgba(255,255,255,0.62)",
  flat: "rgba(255,255,255,0.45)",
  sheet: "rgba(246,247,252,0.94)",
  nav: "rgba(255,255,255,0.55)",
  navBorder: "rgba(255,255,255,0.85)",
  well: "rgba(255,255,255,0.5)",
  divider: "rgba(30,34,51,0.10)",
  scrim: "rgba(30,34,51,0.35)",
  shadow: "rgba(49,46,129,0.10)",
  text: "#1E2233",
  muted: "#475066",
  border: "#7C849A",
  primary: "#4F46E5",
  onPrimary: "#FFFFFF",
  primaryShadow: "rgba(79,70,229,0.30)",
  primaryContainer: "#E1E3FA",
  onPrimaryContainer: "#3730A3",
  success: "#166534",
  warning: "#92400E",
  danger: "#991B1B",
  green: { fg: "#166534", bg: "#E0F2E6" },
  amber: { fg: "#92400E", bg: "#FBF0DA" },
  orange: { fg: "#9A3412", bg: "#FCE8DD" },
  pink: { fg: "#9D174D", bg: "#FAE6EF" },
  teal: { fg: "#115E59", bg: "#DCF1EE" },
  illustration: { amber: "#F59E0B", pink: "#EC4899", teal: "#0F766E", paper: "#FFFFFF" },
  done: "#15803D",
  onDone: "#FFFFFF",
  weekDone: "#B45309",
  onWeekDone: "#FFFFFF",
  wrong: { fg: "#991B1B", bg: "#FADBDB", edge: "#B91C1C" },
  right: { fg: "#166534", bg: "#E0F2E6", edge: "#15803D" },
  der: { fill: "#1D4ED8", onFill: "#FFFFFF", tint: "#E3EBFC", text: "#1E40AF" },
  die: { fill: "#BE123C", onFill: "#FFFFFF", tint: "#FAE3E8", text: "#9F1239" },
  das: { fill: "#0F766E", onFill: "#FFFFFF", tint: "#DCF2EF", text: "#115E59" },
  plural: "#475066",
  names: ["#86198F", "#9A3412", "#115E59", "#5B21B6", "#166534", "#9D174D", "#374151", "#854D0E"],
};

export const dark: Palette = {
  scheme: "dark",
  background: "#151826",
  backdrop: ["#4F46E5", "#0F766E", "#B45309", "#9D174D"],
  backdropOpacity: 0.45,
  card: "rgba(40,46,66,0.55)",
  cardBorder: "rgba(255,255,255,0.10)",
  surface: "rgba(40,46,66,0.55)",
  flat: "rgba(40,46,66,0.35)",
  sheet: "rgba(30,34,52,0.94)",
  nav: "rgba(30,34,52,0.6)",
  navBorder: "rgba(255,255,255,0.10)",
  well: "rgba(255,255,255,0.06)",
  divider: "rgba(255,255,255,0.08)",
  scrim: "rgba(0,0,0,0.5)",
  shadow: "rgba(0,0,0,0.35)",
  text: "#E7E9F3",
  muted: "#A7AEC2",
  border: "#737B93",
  primary: "#A5B4FC",
  onPrimary: "#1E2233",
  primaryShadow: "rgba(165,180,252,0.25)",
  primaryContainer: "#2F3560",
  onPrimaryContainer: "#A5B4FC",
  success: "#4ADE80",
  warning: "#FBBF24",
  danger: "#FCA5A5",
  green: { fg: "#4ADE80", bg: "#1E3A30" },
  amber: { fg: "#FBBF24", bg: "#3D3220" },
  orange: { fg: "#FB923C", bg: "#3F2A22" },
  pink: { fg: "#F472B6", bg: "#3E2335" },
  teal: { fg: "#5EEAD4", bg: "#1C3A3A" },
  illustration: { amber: "#F59E0B", pink: "#EC4899", teal: "#14B8A6", paper: "#323850" },
  done: "#4ADE80",
  onDone: "#1E2233",
  weekDone: "#FBBF24",
  onWeekDone: "#1E2233",
  wrong: { fg: "#FCA5A5", bg: "#43262A", edge: "#F87171" },
  right: { fg: "#4ADE80", bg: "#1E3A30", edge: "#4ADE80" },
  der: { fill: "#93C5FD", onFill: "#1E2233", tint: "#22334F", text: "#93C5FD" },
  die: { fill: "#FDA4AF", onFill: "#1E2233", tint: "#40262F", text: "#FDA4AF" },
  das: { fill: "#5EEAD4", onFill: "#1E2233", tint: "#1C3A3A", text: "#5EEAD4" },
  plural: "#A7AEC2",
  names: ["#F0ABFC", "#FDBA74", "#5EEAD4", "#C4B5FD", "#86EFAC", "#F9A8D4", "#D1D5DB", "#FDE047"],
};

/** The names of the plain text colors, for tables such as "status → color". */
export type ColorToken = "text" | "muted" | "primary" | "success" | "warning" | "danger";

/** A status color token as a tinted pair (text on its pill background), e.g. "success" -> green. */
export function toneAccent(colors: Palette, token: ColorToken): Accent {
  switch (token) {
    case "success":
      return colors.green;
    case "warning":
      return colors.amber;
    case "danger":
      return { fg: colors.wrong.fg, bg: colors.wrong.bg };
    case "primary":
      return { fg: colors.onPrimaryContainer, bg: colors.primaryContainer };
    default:
      return { fg: colors.muted, bg: colors.well };
  }
}

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, section: 28 } as const;

export const radius = { sm: 8, md: 16, lg: 24, card: 28, pill: 999 } as const;

/** The smallest touch target, in dp. */
export const TOUCH = 48;

/**
 * The one font family. Its four weights (400, 600, 700, 800) are faces of this family (see
 * ui/fonts.ts), so `fontWeight` picks the file. Every `Text` from ui/Text.tsx uses it.
 */
export const FONT_FAMILY = "Nunito";

/** The type scale. Nothing smaller than 13, except the nav labels (12). */
export const type = StyleSheet.create({
  headword: { fontSize: 34, lineHeight: 42, fontWeight: "800" },
  greeting: { fontSize: 26, lineHeight: 34, fontWeight: "800" },
  title: { fontSize: 22, lineHeight: 30, fontWeight: "700" },
  section: { fontSize: 17, lineHeight: 24, fontWeight: "700" },
  body: { fontSize: 16, lineHeight: 24, fontWeight: "400" },
  bodyStrong: { fontSize: 16, lineHeight: 24, fontWeight: "700" },
  secondary: { fontSize: 15, lineHeight: 22, fontWeight: "400" },
  small: { fontSize: 14, lineHeight: 20, fontWeight: "600" },
  label: { fontSize: 13, lineHeight: 18, fontWeight: "600" },
  nav: { fontSize: 12, lineHeight: 16, fontWeight: "700" },
});

/** Light by default; the provider in ui/ThemeProvider.tsx supplies the active palette. */
export const ThemeContext = createContext<Palette>(light);

/** The active palette. */
export function useTheme(): Palette {
  return useContext(ThemeContext);
}

/**
 * Styles that follow the theme. Write the styles as a function of the palette, once, outside the
 * component; call the returned hook inside it. Each palette's sheet is built once and reused.
 *
 *   const useStyles = makeStyles((colors) => ({ title: { color: colors.text } }));
 *   function Screen() { const styles = useStyles(); ... }
 */
export function makeStyles<T extends NamedStyles>(factory: (colors: Palette) => T) {
  const sheets = new Map<Palette, T>();
  return function useStyles(): T {
    const colors = useTheme();
    let sheet = sheets.get(colors);
    if (!sheet) {
      sheet = StyleSheet.create(factory(colors));
      sheets.set(colors, sheet);
    }
    return sheet;
  };
}
