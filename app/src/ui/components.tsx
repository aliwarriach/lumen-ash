import { useEffect, useId, useState, type ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  View,
  type StyleProp,
  type TextInputProps,
  type TextStyle,
} from "react-native";

import { Glass } from "@/ui/glass";
import { ICON, type Icon } from "@/ui/icons";
import { Text, TextInput } from "@/ui/Text";
import { makeStyles, radius, space, TOUCH, useTheme, type Accent } from "@/ui/theme";

type ButtonProps = {
  label: string;
  onPress: () => void;
  variant?: "primary" | "secondary" | "danger";
  busy?: boolean;
  disabled?: boolean;
  /** An icon after the label, e.g. an arrow on "Continue". Decorative. */
  icon?: Icon;
};

/**
 * One clear action. Primary is filled (use one per screen), secondary is outlined, danger is
 * outlined in red. At least 48dp tall, with Android's ripple on press.
 */
export function Button({ label, onPress, variant = "primary", busy, disabled, icon: TrailingIcon }: ButtonProps) {
  const styles = useStyles();
  const colors = useTheme();
  const off = disabled || busy;
  const primary = variant === "primary";
  const ink = primary ? colors.onPrimary : variant === "danger" ? colors.danger : colors.text;
  return (
    // The shadow sits outside: the button itself clips the ripple to its rounded corners.
    <View style={[styles.buttonShadow, primary && !off && styles.primaryShadow]}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ disabled: !!off, busy: !!busy }}
        onPress={onPress}
        disabled={off}
        android_ripple={{ color: primary ? colors.onPrimary + "33" : colors.divider }}
        style={[
          styles.button,
          primary && styles.primary,
          variant === "secondary" && styles.secondary,
          variant === "danger" && styles.dangerButton,
          off && styles.off,
        ]}
      >
        {busy ? (
          <ActivityIndicator color={ink} />
        ) : (
          <View style={styles.buttonRow}>
            <Text style={[styles.buttonText, { color: ink }]} numberOfLines={2}>
              {label}
            </Text>
            {TrailingIcon && <TrailingIcon size={ICON.inline} color={ink} />}
          </View>
        )}
      </Pressable>
    </View>
  );
}

/**
 * A text input with its label. The label is tied to the input (Android's "labelled by"), so a
 * screen reader says "German, edit box" and still reads out what has been typed. Setting the
 * label as the input's own description would replace the typed text when it is read back.
 */
export function Field({ label, style, ...props }: TextInputProps & { label: string }) {
  const styles = useStyles();
  const labelId = useId();
  return (
    <View style={styles.field}>
      {label ? (
        <Text nativeID={labelId} style={styles.label}>
          {label}
        </Text>
      ) : null}
      <TextInput
        accessibilityLabelledBy={label ? labelId : undefined}
        style={[styles.input, style]}
        {...props}
      />
    </View>
  );
}

/** A bar from 0 to 1. `color` is the fill (primary by default); `label` is read out with the value. */
export function ProgressBar({ value, color, label }: { value: number; color?: string; label?: string }) {
  const styles = useStyles();
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <View
      style={styles.track}
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      accessibilityValue={{ min: 0, max: 100, now: Math.round(pct) }}
    >
      <View style={[styles.fill, { width: `${pct}%` }, color ? { backgroundColor: color } : null]} />
    </View>
  );
}

type Option<T extends string> = { value: T; label: string };

type ChipRowProps<T extends string> = {
  options: Option<T>[];
  isOn: (value: T) => boolean;
  onPress: (value: T) => void;
  role: "radio" | "checkbox";
  label?: string;
};

/**
 * Outlined chips, filled when on. A chip is 40dp tall; its touch area reaches 48dp beyond the
 * outline, which the 8dp gap between rows leaves room for.
 */
function ChipRow<T extends string>({ options, isOn, onPress, role, label }: ChipRowProps<T>) {
  const styles = useStyles();
  const colors = useTheme();
  return (
    <View style={styles.field}>
      {label && <Text style={styles.label}>{label}</Text>}
      <View style={styles.chips} accessibilityRole={role === "radio" ? "radiogroup" : undefined}>
        {options.map((o) => {
          const on = isOn(o.value);
          return (
            <Pressable
              key={o.value}
              accessibilityRole={role}
              accessibilityState={role === "radio" ? { selected: on } : { checked: on }}
              onPress={() => onPress(o.value)}
              hitSlop={(TOUCH - CHIP_HEIGHT) / 2}
              android_ripple={{ color: colors.divider }}
              style={[styles.chip, on && styles.chipOn]}
            >
              <Text style={[styles.chipText, on && styles.chipTextOn]}>{o.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const CHIP_HEIGHT = 40;

type ChipsProps<T extends string> = {
  options: Option<T>[];
  selected: T | null;
  onSelect: (value: T) => void;
  label?: string;
};

/** A row of single-choice chips, e.g. All / der / die / das. */
export function Chips<T extends string>({ options, selected, onSelect, label }: ChipsProps<T>) {
  return (
    <ChipRow options={options} isOn={(v) => v === selected} onPress={onSelect} role="radio" label={label} />
  );
}

type MultiChipsProps<T extends string> = {
  options: Option<T>[];
  selected: T[];
  onToggle: (value: T) => void;
  label?: string;
};

/** A row of on/off chips, e.g. the chapters a grammar pattern belongs to. */
export function MultiChips<T extends string>({ options, selected, onToggle, label }: MultiChipsProps<T>) {
  return (
    <ChipRow
      options={options}
      isOn={(v) => selected.includes(v)}
      onPress={onToggle}
      role="checkbox"
      label={label}
    />
  );
}

/**
 * A section card. Flat by default: it sits on the page without blur or shadow. `glass` makes it
 * frosted glass, for the one or two cards a screen is about (the plan keeps it to those).
 */
export function Card({
  children,
  glass = false,
  onPress,
  label,
  hint,
}: {
  children: ReactNode;
  glass?: boolean;
  /** Makes the whole card a button, with a ripple. `label` is what a screen reader says. */
  onPress?: () => void;
  label?: string;
  hint?: string;
}) {
  const styles = useStyles();
  const colors = useTheme();
  if (glass) {
    return (
      <Glass onPress={onPress} accessibilityLabel={label} accessibilityHint={hint}>
        {children}
      </Glass>
    );
  }
  if (onPress) {
    return (
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityHint={hint}
        onPress={onPress}
        android_ripple={{ color: colors.divider }}
        style={styles.card}
      >
        {children}
      </Pressable>
    );
  }
  return <View style={styles.card}>{children}</View>;
}

/** A section heading above a group of cards (17, bold). */
export function SectionTitle({ children }: { children: ReactNode }) {
  const styles = useStyles();
  return (
    <Text style={styles.sectionTitle} accessibilityRole="header">
      {children}
    </Text>
  );
}

/** A small tinted label: a status ("Done"), a word type. The text always says it; color adds to it. */
export function Pill({ label, accent, icon: PillIcon }: { label: string; accent: Accent; icon?: Icon }) {
  const styles = useStyles();
  return (
    <View style={[styles.pill, { backgroundColor: accent.bg }]}>
      {PillIcon && <PillIcon size={ICON.small} color={accent.fg} />}
      <Text style={[styles.pillText, { color: accent.fg }]}>{label}</Text>
    </View>
  );
}

type TextLinkProps = { label: string; onPress: () => void; icon?: Icon; hint?: string; tone?: "primary" | "danger" };

/** A text link that is still 48dp tall to touch, with a ripple. */
export function TextLink({ label, onPress, icon: LinkIcon, hint, tone = "primary" }: TextLinkProps) {
  const styles = useStyles();
  const colors = useTheme();
  const ink = tone === "danger" ? colors.danger : colors.primary;
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityHint={hint}
      onPress={onPress}
      android_ripple={{ color: colors.divider }}
      style={styles.linkTarget}
    >
      <Text style={[styles.link, { color: ink }]}>{label}</Text>
      {LinkIcon && <LinkIcon size={ICON.inline} color={ink} />}
    </Pressable>
  );
}

export function Centered({ children }: { children: ReactNode }) {
  const styles = useStyles();
  return <View style={styles.centered}>{children}</View>;
}

const SLOW_AFTER_MS = 8_000;

/** A spinner that says what is happening, and after a few seconds says why it is slow. */
export function Loading({ label = "Loading…" }: { label?: string }) {
  const styles = useStyles();
  const colors = useTheme();
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(timer);
  }, []);
  return (
    <View style={styles.loading}>
      <ActivityIndicator color={colors.primary} />
      <Text style={styles.loadingText}>{label}</Text>
      {slow && (
        <Text style={styles.loadingText}>
          Still working. The server may have been asleep: the first request can take up to a
          minute.
        </Text>
      )}
    </View>
  );
}

type IconLabelProps = {
  icon: Icon;
  /** The icon's color; the text takes its color from `style`. */
  color: string;
  children: ReactNode;
  style?: StyleProp<TextStyle>;
  /** Put the icon after the text, e.g. a ▾ chevron on a "show more" link. */
  trailing?: boolean;
  size?: number;
};

/** An icon with text beside it: a hint with its bulb, "Correct" with its tick. The icon is decorative. */
export function IconLabel({ icon: LabelIcon, color, children, style, trailing, size = ICON.inline }: IconLabelProps) {
  const styles = useStyles();
  const icon = <LabelIcon size={size} color={color} />;
  return (
    <View style={styles.iconLabel}>
      {!trailing && icon}
      <Text style={[styles.iconLabelText, style]}>{children}</Text>
      {trailing && icon}
    </View>
  );
}

/** An error message. A screen reader says it as soon as it appears, without being pointed at it. */
export function ErrorText({ error }: { error: unknown }) {
  const styles = useStyles();
  const message =
    typeof error === "string" ? error : error instanceof Error ? error.message : "Something went wrong";
  return (
    <Text style={styles.error} accessibilityRole="alert" accessibilityLiveRegion="polite">
      {message}
    </Text>
  );
}

const useStyles = makeStyles((colors) => ({
  buttonShadow: { borderRadius: 18 },
  primaryShadow: { boxShadow: `0 6px 18px ${colors.primaryShadow}` },
  button: {
    minHeight: TOUCH + 4,
    borderRadius: 18,
    paddingVertical: space.md,
    paddingHorizontal: space.xl,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1.5,
    borderColor: "transparent",
    overflow: "hidden",
  },
  primary: { backgroundColor: colors.primary },
  secondary: { backgroundColor: colors.well, borderColor: colors.border },
  dangerButton: { backgroundColor: colors.well, borderColor: colors.danger },
  off: { opacity: 0.5 },
  buttonRow: { flexDirection: "row", alignItems: "center", gap: space.sm + 2 },
  buttonText: { fontSize: 16, lineHeight: 22, fontWeight: "700", flexShrink: 1, textAlign: "center" },
  field: { gap: space.sm },
  label: { fontSize: 14, lineHeight: 20, fontWeight: "600", color: colors.muted },
  input: {
    minHeight: TOUCH + 4,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    fontSize: 16,
  },
  track: { height: 8, borderRadius: 4, backgroundColor: colors.divider, overflow: "hidden" },
  fill: { height: 8, borderRadius: 4, backgroundColor: colors.primary },
  card: {
    backgroundColor: colors.flat,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: space.lg + space.xs,
    gap: space.md,
    overflow: "hidden",
  },
  sectionTitle: { fontSize: 17, lineHeight: 24, fontWeight: "800", marginHorizontal: space.xs },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: space.xs,
    minHeight: 28,
    paddingHorizontal: 10,
    borderRadius: 14,
  },
  pillText: { fontSize: 13, lineHeight: 18, fontWeight: "700" },
  linkTarget: {
    minHeight: TOUCH,
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: space.xs,
    paddingRight: space.sm,
    borderRadius: radius.sm,
    overflow: "hidden",
  },
  link: { fontSize: 15, lineHeight: 22, fontWeight: "700", color: colors.primary },
  centered: { flex: 1, alignItems: "center", justifyContent: "center", padding: space.xl },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  chip: {
    minHeight: CHIP_HEIGHT,
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: space.lg,
    overflow: "hidden",
  },
  chipOn: { backgroundColor: colors.primaryContainer, borderColor: colors.primaryContainer },
  chipText: { fontSize: 15, lineHeight: 20, fontWeight: "600" },
  chipTextOn: { color: colors.onPrimaryContainer, fontWeight: "700" },
  error: { color: colors.danger, fontSize: 15, lineHeight: 22 },
  iconLabel: { flexDirection: "row", alignItems: "center", gap: space.sm },
  iconLabelText: { flexShrink: 1 },
  loading: { alignItems: "center", gap: space.sm },
  loadingText: { color: colors.muted, fontSize: 14, lineHeight: 20, textAlign: "center" },
}));
