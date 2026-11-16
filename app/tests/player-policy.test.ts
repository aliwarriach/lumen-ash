// Run with `npm test`.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  canShowInApp,
  decide,
  describeHttpError,
  parseWebUrl,
  sameSite,
  siteOf,
} from "../src/features/player/policy";

const SAVED = "https://app.allango.net/book?page=8&id=42&type=audio";

test("web links are parsed, anything else is not", () => {
  assert.deepEqual(parseWebUrl("HTTPS://App.Allango.NET:8443/x?y=1"), {
    scheme: "https",
    host: "app.allango.net",
  });
  assert.deepEqual(parseWebUrl(" http://example.com "), { scheme: "http", host: "example.com" });
  assert.deepEqual(parseWebUrl("https://example.com#top"), { scheme: "https", host: "example.com" });
  for (const bad of [
    "javascript:alert(1)",
    "intent://scan/#Intent;scheme=zxing;end",
    "file:///data/user/0/x",
    "data:text/html,hi",
    "https://",
    "https://user@evil.com/",
    "https://allango.net@evil.com/",
    "https://[::1]/",
    "ftp://example.com",
    "not a url",
    "",
  ]) {
    assert.equal(parseWebUrl(bad), null, bad);
  }
});

test("a site is its main domain, with the usual two-part endings", () => {
  assert.equal(siteOf("app.allango.net"), "allango.net");
  assert.equal(siteOf("allango.net"), "allango.net");
  assert.equal(siteOf("shop.example.co.uk"), "example.co.uk");
  assert.equal(siteOf("192.168.1.5"), "192.168.1.5");
  assert.equal(sameSite("login.allango.net", "app.allango.net"), true);
  assert.equal(sameSite("allango.net.evil.com", "allango.net"), false);
  assert.equal(sameSite("evilallango.net", "allango.net"), false);
});

test("the page may move around its own site, over https", () => {
  assert.equal(decide("https://app.allango.net/next?page=9", SAVED), "allow");
  assert.equal(decide("https://login.allango.net/", SAVED), "allow");
  assert.equal(decide("about:blank", SAVED), "allow");
});

test("Allango's sign-in server stays in the app, but only for Allango pages", () => {
  const sso = "https://sso.dialogcrm.cloud/realms/EKS/protocol/openid-connect/auth";
  assert.equal(decide(sso, SAVED), "allow");
  assert.equal(decide(sso, "https://www.allango.net/product/x?page=8"), "allow");
  assert.equal(decide("http://sso.dialogcrm.cloud/", SAVED), "external"); // not secure
  assert.equal(decide("https://dialogcrm.cloud.evil.com/", SAVED), "external");
  assert.equal(decide("https://evildialogcrm.cloud/", SAVED), "external");
  // Another saved site gets no such partner.
  assert.equal(decide(sso, "https://example.com/page"), "external");
});

test("other sites and insecure pages go to the phone's browser", () => {
  assert.equal(decide("https://www.klett.de/", SAVED), "external");
  assert.equal(decide("https://allango.net.evil.com/", SAVED), "external");
  assert.equal(decide("http://app.allango.net/", SAVED), "external");
  assert.equal(decide("https://example.com/", "not a link"), "external");
});

test("things that aren't web links are refused", () => {
  assert.equal(decide("intent://x#Intent;end", SAVED), "block");
  assert.equal(decide("javascript:alert(1)", SAVED), "block");
  assert.equal(decide("file:///etc/hosts", SAVED), "block");
  assert.equal(decide("https://allango.net@evil.com/", SAVED), "block");
});

test("only secure links are shown in the app", () => {
  assert.equal(canShowInApp(SAVED), true);
  assert.equal(canShowInApp("http://app.allango.net/"), false);
  assert.equal(canShowInApp(null), false);
  assert.equal(canShowInApp("javascript:alert(1)"), false);
});

test("errors say what to do", () => {
  assert.match(describeHttpError(403), /Open it in your browser/);
  assert.match(describeHttpError(404), /wasn't found/);
  assert.match(describeHttpError(503), /Try again/);
  assert.match(describeHttpError(418), /error 418/);
});
