// When another app shares to this one, expo-share-intent opens a link like "lumen://dataUrl=...".
// That isn't a screen, so send it to the home screen: the layout notices the shared message and
// opens the capture screen from there.
export function redirectSystemPath({ path }: { path: string; initial: boolean }): string {
  return path.includes("dataUrl=") ? "/" : path;
}
