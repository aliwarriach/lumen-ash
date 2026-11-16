/** The phone's IANA timezone, e.g. "Asia/Karachi". Used for "today" in review limits. */
export function deviceTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}
