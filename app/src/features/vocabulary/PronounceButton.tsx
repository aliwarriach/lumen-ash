import { useAudioPlayer, useAudioPlayerStatus } from "expo-audio";
import { useEffect } from "react";
import * as Speech from "expo-speech";
import { Pressable } from "react-native";

import { ICON, Volume2 } from "@/ui/icons";
import { Text } from "@/ui/Text";
import { makeStyles, radius, space, TOUCH, useTheme } from "@/ui/theme";

type Props = {
  /** What to say, e.g. "der Tisch". Used by the phone's voice when there's no recording. */
  text: string;
  /** A native-speaker recording from Wikimedia Commons, if the dictionary had one. */
  audioUrl?: string | null;
};

/** Speaks with an installed German voice if there is one; says so in the log if there is none. */
async function speakGerman(text: string) {
  await Speech.stop();
  let voice: string | undefined;
  try {
    const voices = (await Speech.getAvailableVoicesAsync()).filter((v) => v.language.toLowerCase().startsWith("de"));
    // Prefer standard German (de-DE) over Austrian or Swiss, and a higher quality voice.
    voices.sort(
      (a, b) =>
        Number(b.language.toLowerCase() === "de-de") - Number(a.language.toLowerCase() === "de-de") ||
        Number(b.quality === "Enhanced") - Number(a.quality === "Enhanced"),
    );
    voice = voices[0]?.identifier;
    if (__DEV__) console.log("[speech] German voices on this phone:", voices.map((v) => `${v.identifier} (${v.language})`));
  } catch {
    // Some phones can't list voices: speak with the language alone.
  }
  Speech.speak(text, { language: "de-DE", voice, rate: 0.9 });
}

/**
 * Plays the real recording when it has loaded, otherwise the phone's German voice, so a tap always
 * makes a sound. The label says which one you will hear.
 */
export function PronounceButton({ text, audioUrl }: Props) {
  const colors = useTheme();
  const styles = useStyles();
  // downloadFirst: fetch the whole (tiny) recording before playing, instead of streaming it.
  const player = useAudioPlayer(audioUrl ?? null, { downloadFirst: true });
  const status = useAudioPlayerStatus(player);
  const hasRecording = audioUrl != null && status.isLoaded;

  // Development only: why a recording does or doesn't load.
  useEffect(() => {
    if (!__DEV__ || audioUrl == null) return;
    console.log("[audio] status", {
      state: status.playbackState,
      loaded: status.isLoaded,
      waiting: status.reasonForWaitingToPlay,
      buffering: status.isBuffering,
      duration: status.duration,
    });
  }, [audioUrl, status.playbackState, status.isLoaded, status.reasonForWaitingToPlay, status.isBuffering, status.duration]);

  function speak() {
    if (__DEV__) {
      console.log("[audio]", { recording: audioUrl != null, loaded: status.isLoaded, playing: status.playing });
    }
    if (hasRecording) {
      // Play at once. A recording that already played is rewound first, but the rewind is not
      // waited for: a seek that never finishes must not stop the sound.
      if (status.currentTime > 0) player.seekTo(0).catch(() => undefined);
      player.play();
    } else {
      void speakGerman(text);
    }
  }

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`Pronounce ${text}`}
      onPress={speak}
      android_ripple={{ color: colors.divider }}
      style={styles.button}
    >
      <Volume2 size={ICON.inline} color={colors.onPrimaryContainer} />
      <Text style={styles.label}>{hasRecording ? "Native speaker" : "Phone voice"}</Text>
    </Pressable>
  );
}

const useStyles = makeStyles((colors) => ({
  button: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    alignSelf: "flex-start",
    minHeight: TOUCH,
    paddingHorizontal: space.lg,
    borderRadius: radius.md,
    backgroundColor: colors.primaryContainer,
    overflow: "hidden",
  },
  label: { color: colors.onPrimaryContainer, fontSize: 14, lineHeight: 20, fontWeight: "700" },
}));
