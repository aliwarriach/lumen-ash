// The same rules as the server (backend/app/community/schemas.py), so a bad username is caught
// before the request. The server stays the judge: it also knows the reserved names and who has
// which name already.

export const USERNAME_MIN = 3;
export const USERNAME_MAX = 20;

const ALLOWED = /^[A-Za-z0-9_äöüßÄÖÜ]+$/;
const LETTER = /[A-Za-zäöüßÄÖÜ]/;

/** What is wrong with this username, in words for the person, or null if it looks fine. */
export function usernameProblem(raw: string): string | null {
  const name = raw.trim();
  if (name.length < USERNAME_MIN || name.length > USERNAME_MAX) {
    return `A username must be ${USERNAME_MIN} to ${USERNAME_MAX} characters.`;
  }
  if (!ALLOWED.test(name)) return "Use only letters, numbers and underscores (_), with no spaces.";
  if (!LETTER.test(name)) return "A username needs at least one letter.";
  return null;
}
