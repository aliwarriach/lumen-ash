// One import per weight: the package root would bundle all 16 Nunito files (about 2 MB).
import { Nunito_400Regular } from "@expo-google-fonts/nunito/400Regular";
import { Nunito_600SemiBold } from "@expo-google-fonts/nunito/600SemiBold";
import { Nunito_700Bold } from "@expo-google-fonts/nunito/700Bold";
import { Nunito_800ExtraBold } from "@expo-google-fonts/nunito/800ExtraBold";
import type { FontMap } from "expo-font";

import { FONT_FAMILY } from "@/ui/theme";

/**
 * Nunito, in the four weights the design uses (it has ä ö ü ß). All four are faces of one family,
 * so `fontWeight: "700"` picks the bold file: a family loads once, so they must be declared together.
 * (On Android below version 10 only the regular face loads; the learner's phone is newer.)
 */
export const APP_FONTS: FontMap = [
  {
    fontFamily: FONT_FAMILY,
    fontDefinitions: [
      { path: Nunito_400Regular, weight: 400 },
      { path: Nunito_600SemiBold, weight: 600 },
      { path: Nunito_700Bold, weight: 700 },
      { path: Nunito_800ExtraBold, weight: 800 },
    ],
  },
];
