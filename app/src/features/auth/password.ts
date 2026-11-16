export const PASSWORD_MIN = 8;

/** What is wrong with a new password, or null. Supabase may ask for more; its message is shown then. */
export function passwordProblem(password: string, again: string): string | null {
  if (password.length < PASSWORD_MIN) return `Use at least ${PASSWORD_MIN} characters for the password.`;
  if (password !== again) return "The two passwords are not the same.";
  return null;
}

export function looksLikeEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}
