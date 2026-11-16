import { View } from "react-native";
import Svg, { Circle, Path, Rect } from "react-native-svg";

import { Text } from "@/ui/Text";
import { makeStyles, useTheme } from "@/ui/theme";

const W = 104;
const H = 92;

/**
 * The picture on Today's main card: an open book with a "Hallo!" speech bubble and a few sparkles,
 * drawn in the theme's colors (from the approved preview). Decorative, so screen readers skip it.
 *
 * The word sits on top as app text rather than SVG text, so it uses the loaded Nunito face.
 */
export function TodayIllustration() {
  const colors = useTheme();
  const styles = useStyles();
  const ink = colors.primary;
  return (
    <View style={styles.box} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
        <Circle cx={56} cy={50} r={40} fill={colors.primaryContainer} />
        <Path
          d="M20 62 Q38 54 54 62 L54 84 Q38 76 20 84 Z"
          fill={colors.illustration.paper}
          stroke={ink}
          strokeWidth={2.5}
          strokeLinejoin="round"
        />
        <Path
          d="M88 62 Q70 54 54 62 L54 84 Q70 76 88 84 Z"
          fill={colors.illustration.paper}
          stroke={ink}
          strokeWidth={2.5}
          strokeLinejoin="round"
        />
        <Path
          d="M27 66 Q38 62 48 66 M27 72 Q38 68 48 72 M60 66 Q70 62 81 66"
          stroke={colors.border}
          strokeWidth={2}
          fill="none"
          strokeLinecap="round"
        />
        <Rect x={44} y={12} width={56} height={30} rx={12} fill={ink} />
        <Path d="M56 41 L52 50 L64 41 Z" fill={ink} />
        <Path d="M18 20 l3 6 6 3 -6 3 -3 6 -3 -6 -6 -3 6 -3 z" fill={colors.illustration.amber} />
        <Circle cx={32} cy={42} r={3.5} fill={colors.illustration.pink} />
        <Circle cx={98} cy={54} r={3} fill={colors.illustration.teal} />
      </Svg>
      <Text style={styles.hallo} allowFontScaling={false}>
        Hallo!
      </Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  box: { width: W, height: H },
  // Over the bubble (x 44-100, y 12-42).
  hallo: {
    position: "absolute",
    left: 44,
    top: 12,
    width: 56,
    height: 30,
    lineHeight: 30,
    textAlign: "center",
    fontSize: 14,
    fontWeight: "800",
    color: colors.onPrimary,
  },
}));
