import { useEffect, useState } from "react";
import { Keyboard } from "react-native";

/**
 * Whether the on-screen keyboard is showing. Used to add the navigation bar's height under an
 * input only while the keyboard is closed: with it open, the keyboard already covers that area and
 * adding the height again leaves a gap above the keyboard.
 */
export function useKeyboardOpen(): boolean {
  const [open, setOpen] = useState(Keyboard.isVisible());
  useEffect(() => {
    const show = Keyboard.addListener("keyboardDidShow", () => setOpen(true));
    const hide = Keyboard.addListener("keyboardDidHide", () => setOpen(false));
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);
  return open;
}
