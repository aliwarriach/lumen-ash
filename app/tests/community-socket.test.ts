// Run with `npm test`. The chat socket's behaviour with a fake WebSocket and fake timers.
import assert from "node:assert/strict";
import { afterEach, beforeEach, mock, test } from "node:test";

import {
  CommunitySocket,
  MAX_BACKOFF_MS,
  PING_EVERY_MS,
  READY_TIMEOUT_MS,
  SILENCE_LIMIT_MS,
  backoffDelay,
  socketUrl,
  type SocketLike,
  type SocketState,
} from "../src/features/community/socket";
import type { CommunityMessage } from "../src/features/community/store";

class FakeSocket implements SocketLike {
  onopen: ((e: unknown) => void) | null = null;
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  sent: unknown[] = [];
  closedWith: number | undefined | "open" = "open";
  constructor(readonly url: string) {}
  send(data: string) {
    this.sent.push(JSON.parse(data));
  }
  close(code?: number) {
    this.closedWith = code;
  }
  // the server's side
  open() {
    this.onopen?.({});
  }
  push(frame: object) {
    this.onmessage?.({ data: JSON.stringify(frame) });
  }
  serverClose(code: number) {
    this.onclose?.({ code });
  }
}

let sockets: FakeSocket[];
let states: SocketState[];
let online: number[];
let received: CommunityMessage[];
let readies: number;
let token: string | null;

function make() {
  return new CommunitySocket(
    {
      url: "wss://api.test/community/ws",
      getToken: async () => token,
      createSocket: (url) => {
        const s = new FakeSocket(url);
        sockets.push(s);
        return s;
      },
      onState: (s) => states.push(s),
      onOnline: (n) => online.push(n),
      onMessage: (m) => received.push(m),
      onReady: () => readies++,
    },
    () => 0.5, // no spread: a delay is exactly the base
  );
}

/** Lets the promise inside connect() (getToken) finish. */
const settle = () => new Promise<void>((resolve) => setImmediate(resolve));

async function connectAndReady(client: CommunitySocket): Promise<FakeSocket> {
  client.start();
  await settle();
  const s = sockets[sockets.length - 1];
  s.open();
  s.push({ type: "ready", online: 3 });
  return s;
}

beforeEach(() => {
  sockets = [];
  states = [];
  online = [];
  received = [];
  readies = 0;
  token = "tok-1";
  mock.timers.enable({ apis: ["setTimeout", "setInterval", "Date"] });
});
afterEach(() => mock.timers.reset());

test("the first frame sent is the auth frame with the token", async () => {
  const client = make();
  client.start();
  await settle();
  assert.equal(sockets.length, 1);
  assert.equal(sockets[0].url, "wss://api.test/community/ws");
  sockets[0].open();
  assert.deepEqual(sockets[0].sent, [{ type: "auth", token: "tok-1" }]);
  client.stop();
});

test("it counts as live only after the server says ready", async () => {
  const client = make();
  client.start();
  await settle();
  sockets[0].open();
  assert.equal(states.at(-1), "connecting");
  sockets[0].push({ type: "ready", online: 7 });
  assert.equal(states.at(-1), "live");
  assert.deepEqual(online, [7]);
  assert.equal(readies, 1);
  client.stop();
});

test("pushed messages and presence reach the handlers; junk is ignored", async () => {
  const client = make();
  const s = await connectAndReady(client);
  const m = { id: "m1" } as CommunityMessage;
  s.push({ type: "message", message: m });
  s.push({ type: "presence", online: 5 });
  s.push({ type: "pong" });
  s.onmessage?.({ data: "not json" });
  s.onmessage?.({ data: 42 });
  assert.deepEqual(received, [m]);
  assert.deepEqual(online, [3, 5]);
  client.stop();
});

test("it pings every 25 seconds while the server keeps answering", async () => {
  const client = make();
  const s = await connectAndReady(client);
  for (let i = 0; i < 4; i++) {
    mock.timers.tick(PING_EVERY_MS);
    s.push({ type: "pong" });
  }
  assert.equal(s.sent.filter((f) => (f as { type: string }).type === "ping").length, 4);
  assert.equal(sockets.length, 1, "a healthy connection is never replaced");
  client.stop();
});

test("a connection that goes silent is closed and replaced", async () => {
  const client = make();
  const s = await connectAndReady(client);
  // the server never answers a ping
  mock.timers.tick(PING_EVERY_MS * Math.ceil(SILENCE_LIMIT_MS / PING_EVERY_MS) + PING_EVERY_MS);
  assert.notEqual(s.closedWith, "open", "the dead socket was closed");
  assert.equal(states.at(-1), "offline");
  mock.timers.tick(1000); // first backoff
  await settle();
  assert.equal(sockets.length, 2);
  client.stop();
});

test("a server that never says ready is given up on", async () => {
  const client = make();
  client.start();
  await settle();
  sockets[0].open();
  mock.timers.tick(READY_TIMEOUT_MS);
  assert.equal(states.at(-1), "offline");
  mock.timers.tick(1000);
  await settle();
  assert.equal(sockets.length, 2);
  client.stop();
});

test("reconnecting backs off 1 s, 2 s, 4 s, and a good connection resets it", async () => {
  const client = make();
  client.start();
  await settle();
  sockets[0].serverClose(1006);
  mock.timers.tick(999);
  await settle();
  assert.equal(sockets.length, 1, "not before 1 s");
  mock.timers.tick(1);
  await settle();
  assert.equal(sockets.length, 2);

  sockets[1].serverClose(1006);
  mock.timers.tick(1999);
  await settle();
  assert.equal(sockets.length, 2, "not before 2 s");
  mock.timers.tick(1);
  await settle();
  assert.equal(sockets.length, 3);

  sockets[2].open();
  sockets[2].push({ type: "ready", online: 1 });
  sockets[2].serverClose(1006);
  mock.timers.tick(1000); // back to 1 s after a connection that worked
  await settle();
  assert.equal(sockets.length, 4);
  client.stop();
});

test("the delay grows to a limit and is spread so phones don't all return together", () => {
  assert.equal(backoffDelay(0, 0.5), 1000);
  assert.equal(backoffDelay(1, 0.5), 2000);
  assert.equal(backoffDelay(2, 0.5), 4000);
  assert.equal(backoffDelay(20, 0.5), MAX_BACKOFF_MS);
  assert.equal(backoffDelay(0, 0), 750);
  assert.equal(backoffDelay(0, 1), 1250);
});

test("after 4401 (login ran out) it reconnects at once the first time, then backs off", async () => {
  const client = make();
  client.start();
  await settle();
  sockets[0].serverClose(4401);
  await settle();
  assert.equal(sockets.length, 2, "straight away, no waiting");
  sockets[1].serverClose(4401);
  await settle();
  assert.equal(sockets.length, 2, "the second time it waits");
  mock.timers.tick(1000);
  await settle();
  assert.equal(sockets.length, 3);
  client.stop();
});

test("the same account on a 4th place waits the longest instead of fighting for the slot", async () => {
  const client = make();
  client.start();
  await settle();
  sockets[0].serverClose(4409);
  mock.timers.tick(MAX_BACKOFF_MS - 1);
  await settle();
  assert.equal(sockets.length, 1);
  mock.timers.tick(1);
  await settle();
  assert.equal(sockets.length, 2);
  client.stop();
});

test("signed out (no token): no socket is opened, it keeps trying", async () => {
  token = null;
  const client = make();
  client.start();
  await settle();
  assert.equal(sockets.length, 0);
  token = "tok-2";
  mock.timers.tick(1000);
  await settle();
  assert.equal(sockets.length, 1);
  client.stop();
});

test("stop() closes the socket, ends the timers and ignores anything the old socket still says", async () => {
  const client = make();
  const s = await connectAndReady(client);
  client.stop();
  assert.equal(s.closedWith, 1000);
  assert.equal(states.at(-1), "offline");
  s.onmessage?.({ data: JSON.stringify({ type: "message", message: { id: "late" } }) });
  s.onclose?.({ code: 1006 });
  mock.timers.tick(MAX_BACKOFF_MS * 2);
  await settle();
  assert.deepEqual(received, []);
  assert.equal(sockets.length, 1, "no reconnect after stop");
});

test("stop() while waiting for the token never opens a socket", async () => {
  const client = make();
  client.start();
  client.stop();
  await settle();
  assert.equal(sockets.length, 0);
});

test("start() twice is one connection", async () => {
  const client = make();
  client.start();
  client.start();
  await settle();
  assert.equal(sockets.length, 1);
  client.stop();
});

test("the socket address comes from the API address", () => {
  assert.equal(socketUrl("https://api.example.com"), "wss://api.example.com/community/ws");
  assert.equal(socketUrl("http://10.0.2.2:8000/"), "ws://10.0.2.2:8000/community/ws");
});
