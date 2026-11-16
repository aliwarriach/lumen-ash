/**
 * The app's icons: one family (Lucide, outlined, ISC license), drawn as SVG.
 *
 * Each icon is imported from its own file: importing from the package root would put all of
 * Lucide's ~1,500 icons in the app, because the bundler keeps whole modules. Add new icons here,
 * never as text glyphs or emoji (the audit's first finding).
 *
 * Icons are decorative unless the control around them has its own accessibility label.
 */
export { default as ArrowDown } from "lucide-react-native/icons/arrow-down";
export { default as ArrowRight } from "lucide-react-native/icons/arrow-right";
export { default as Award } from "lucide-react-native/icons/award";
export { default as BookA } from "lucide-react-native/icons/book-a";
export { default as BookOpen } from "lucide-react-native/icons/book-open";
export { default as Check } from "lucide-react-native/icons/check";
export { default as ChevronDown } from "lucide-react-native/icons/chevron-down";
export { default as ChevronLeft } from "lucide-react-native/icons/chevron-left";
export { default as ChevronRight } from "lucide-react-native/icons/chevron-right";
export { default as ChevronUp } from "lucide-react-native/icons/chevron-up";
export { default as CircleUserRound } from "lucide-react-native/icons/circle-user-round";
export { default as ClipboardList } from "lucide-react-native/icons/clipboard-list";
export { default as Copy } from "lucide-react-native/icons/copy";
export { default as Dumbbell } from "lucide-react-native/icons/dumbbell";
export { default as ExternalLink } from "lucide-react-native/icons/external-link";
export { default as EllipsisVertical } from "lucide-react-native/icons/ellipsis-vertical";
export { default as Flag } from "lucide-react-native/icons/flag";
export { default as Flame } from "lucide-react-native/icons/flame";
export { default as Hand } from "lucide-react-native/icons/hand";
export { default as Lightbulb } from "lucide-react-native/icons/lightbulb";
export { default as MessagesSquare } from "lucide-react-native/icons/messages-square";
export { default as Moon } from "lucide-react-native/icons/moon";
export { default as PartyPopper } from "lucide-react-native/icons/party-popper";
export { default as PenLine } from "lucide-react-native/icons/pen-line";
export { default as Plus } from "lucide-react-native/icons/plus";
export { default as Repeat2 } from "lucide-react-native/icons/repeat-2";
export { default as Rocket } from "lucide-react-native/icons/rocket";
export { default as RotateCcw } from "lucide-react-native/icons/rotate-ccw";
export { default as RotateCw } from "lucide-react-native/icons/rotate-cw";
export { default as ScanText } from "lucide-react-native/icons/scan-text";
export { default as Search } from "lucide-react-native/icons/search";
export { default as SpellCheck } from "lucide-react-native/icons/spell-check";
export { default as Sun } from "lucide-react-native/icons/sun";
export { default as ThumbsUp } from "lucide-react-native/icons/thumbs-up";
export { default as Volume2 } from "lucide-react-native/icons/volume-2";
export { default as X } from "lucide-react-native/icons/x";

export type { LucideIcon as Icon } from "lucide-react-native";

/**
 * Sizes, in dp: 28 in an illustration-like badge, 24 in bars and lists, 22 for the tick in a
 * checkbox, 20 next to text, 18 in a small pill, 16 inside the smallest labels.
 * Strokes: every icon uses Lucide's default 2; only tick and cross marks use 3.
 */
export const ICON = { large: 28, bar: 24, mark: 22, inline: 20, badge: 18, small: 16 } as const;
