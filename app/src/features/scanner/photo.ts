// Takes or picks a photo and reads its text ON THE PHONE (Google ML Kit, through
// expo-text-extractor). The photo is never uploaded and is deleted as soon as it has been read.
//
// Both native modules are loaded when first used, not at start-up: in Expo Go the text reader isn't
// there, and that must only disable photo reading, not crash the screen.
import * as ImagePicker from "expo-image-picker";

import { cleanReading, joinBlocks } from "@/features/scanner/text";

export type PhotoResult =
  | { kind: "text"; text: string }
  | { kind: "cancelled" }
  | { kind: "failed"; message: string };

const NOT_INSTALLED =
  "Reading photos needs the installed app: it doesn't work in Expo Go. You can type or paste the exercise instead.";
const UNREADABLE =
  "I couldn't read that photo. Try again closer, in good light, with the page flat. Or type the exercise instead.";
const NO_CAMERA =
  "The camera isn't allowed. Allow it in your phone's settings for this app, or choose a photo from your gallery.";

// Cropping is on so the learner can cut the page down to the one exercise: less to read and
// correct, and no neighbours' names from a shared worksheet.
const PICKER_OPTIONS: ImagePicker.ImagePickerOptions = {
  mediaTypes: ["images"],
  allowsEditing: true,
  quality: 1,
};

export async function takePhoto(): Promise<PhotoResult> {
  const permission = await ImagePicker.requestCameraPermissionsAsync();
  if (!permission.granted) return { kind: "failed", message: NO_CAMERA };
  return fromPicker(await ImagePicker.launchCameraAsync(PICKER_OPTIONS));
}

export async function choosePhoto(): Promise<PhotoResult> {
  return fromPicker(await ImagePicker.launchImageLibraryAsync(PICKER_OPTIONS));
}

/**
 * Android can close the app while the camera is open. The photo is then waiting for us when the
 * app starts again: pick it up so the learner doesn't have to start over.
 */
export async function pendingPhoto(): Promise<PhotoResult | null> {
  const pending = await ImagePicker.getPendingResultAsync();
  if (!pending) return null;
  if ("code" in pending) return { kind: "failed", message: UNREADABLE };
  return fromPicker(pending);
}

async function fromPicker(result: ImagePicker.ImagePickerResult): Promise<PhotoResult> {
  const uri = result.assets?.[0]?.uri;
  if (result.canceled || !uri) return { kind: "cancelled" };
  try {
    return await read(uri);
  } finally {
    await discard(uri);
  }
}

async function read(uri: string): Promise<PhotoResult> {
  let extractor: typeof import("expo-text-extractor");
  try {
    extractor = await import("expo-text-extractor");
    if (!extractor.isSupported) return { kind: "failed", message: NOT_INSTALLED };
  } catch {
    return { kind: "failed", message: NOT_INSTALLED };
  }
  try {
    // Typical misreads (ß, Ich, gaps, split words) are put right before the learner sees the text.
    const text = cleanReading(joinBlocks(await extractor.extractTextFromImage(uri)));
    return text ? { kind: "text", text } : { kind: "failed", message: UNREADABLE };
  } catch {
    return { kind: "failed", message: UNREADABLE };
  }
}

/** The photo is kept only while it is being read. Only our own cache copy is ever deleted. */
async function discard(uri: string): Promise<void> {
  try {
    const { File, Paths } = await import("expo-file-system");
    if (uri.startsWith(Paths.cache.uri)) new File(uri).delete();
  } catch {
    // The system clears its cache itself. Not being able to tidy up must not fail the read.
  }
}
