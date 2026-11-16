// What the in-app page may do. Pure functions, no React Native imports, so `npm test` can run them.
//
// The player shows a page the learner saved themselves (an Allango link). That page may load its
// own scripts and media, and move around its own site, but it must not turn the app into a general
// browser: other sites open in the phone's browser, and anything that isn't a web link (intent:,
// file:, javascript:, data: ...) is refused.

export type Decision = "allow" | "external" | "block";

type Parsed = { scheme: "http" | "https"; host: string };

// scheme://host[:port] followed by / ? # or the end. No user@ part: "https://a.com@evil.com" is
// really evil.com, so any address with an @ before the path is refused rather than interpreted.
const WEB_URL = /^(https?):\/\/([^/?#@\s]+)(?:[/?#]|$)/i;
const SECOND_LEVEL = new Set(["co", "com", "org", "net", "ac", "gov", "edu"]);

export function parseWebUrl(url: string): Parsed | null {
  const m = WEB_URL.exec(url.trim());
  if (!m) return null;
  const host = m[2].replace(/:\d+$/, "").toLowerCase();
  if (!host || host.includes(":")) return null; // IPv6 and odd ports
  return { scheme: m[1].toLowerCase() as Parsed["scheme"], host };
}

/** "app.allango.net" → "allango.net"; "shop.example.co.uk" → "example.co.uk". IP addresses stay whole. */
export function siteOf(host: string): string {
  if (/^\d+(\.\d+){3}$/.test(host)) return host;
  const labels = host.split(".");
  const keep = labels.length >= 3 && SECOND_LEVEL.has(labels[labels.length - 2]) ? 3 : 2;
  return labels.slice(-keep).join(".");
}

/** Whether two hosts belong to the same site (the page and its own sub-domains). */
export function sameSite(a: string, b: string): boolean {
  return siteOf(a) === siteOf(b);
}

// Other domains a saved link's site may sign in through, by the saved link's site.
const SIGN_IN_PARTNERS: Record<string, readonly string[]> = {
  "allango.net": ["dialogcrm.cloud"], // Klett's sign-in server (sso.dialogcrm.cloud)
};

/**
 * What to do with a navigation inside the player.
 *  allow     stay in the app: a secure page on the same site as the saved link, or on a sign-in
 *            partner of that site
 *  external  hand to the phone's browser: another site, or an insecure (http) page
 *  block     do nothing: not a web link at all
 */
export function decide(target: string, savedLink: string): Decision {
  if (target === "about:blank") return "allow";
  const to = parseWebUrl(target);
  if (!to) return "block";
  const from = parseWebUrl(savedLink);
  if (to.scheme !== "https" || !from) return "external";
  if (sameSite(to.host, from.host)) return "allow";
  // Allango signs the learner in through a server on another domain (found in the first test on a
  // phone: the page redirected to it on opening, the app sent that to the browser, and the audio
  // never loaded). Only that partner is added; any other site still goes to the browser.
  if (SIGN_IN_PARTNERS[siteOf(from.host)]?.includes(siteOf(to.host))) return "allow";
  return "external";
}

/** Whether a saved link can be shown in the app at all (secure web links only). */
export function canShowInApp(link: string | null): link is string {
  return link !== null && parseWebUrl(link)?.scheme === "https";
}

/** A page that answered with an error: say so, and say what to do. */
export function describeHttpError(status: number): string {
  if (status === 401 || status === 403) {
    return "The site refused to open this page here. It may need you to sign in, or it may block in-app views. Open it in your browser instead.";
  }
  if (status === 404) return "This page wasn't found. The link may be old.";
  if (status >= 500) return "The site had a problem. Try again in a moment.";
  return `The page didn't load (error ${status}). Open it in your browser instead.`;
}
