import * as Haptics from "expo-haptics";

/**
 * A short success buzz. Only for real wins (a finished session, a perfect round), never for every
 * tap: constant vibration is noise, and the learner can switch the phone's touch feedback off.
 */
export function winHaptic(): void {
  Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
}
