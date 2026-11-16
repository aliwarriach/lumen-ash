// The phone's end of GET /community/ws: a connection that keeps itself alive and comes back by
// itself. The socket only ever PUSHES (new and deleted messages, how many people are here);
// posting and deleting are ordinary requests. Nothing here is trusted to be complete: the chat
// also asks "anything new?" on a timer (useCommunity.ts), so a dropped push costs a few seconds,
// never a message.
//
// No React Native imports: the WebSocket, the sign-in and the clock are passed in, so the tests
// run it with a fake socket and fake timers.
import type { CommunityMessage } from "./store";

export type SocketState = "connecting" | "live" | "offline";

/** The part of WebSocket this client uses (React Native's built-in one has it). */
export interface SocketLike {
  onopen: ((event: unknown) => void) | null;
  onmessage: ((event: { data: unknown }) => void) | null;
  onclose: ((event: { code: number }) => void) | null;
  onerror: ((event: unknown) => void) | null;
  send(data: string): void;
  close(code?: number, reason?: string): void;
}

export type SocketOptions = {
  /** `wss://…/community/ws` */
  url: string;
  /** The current Supabase access token (refreshed if it ran out), or null when signed out. */
  getToken: () => Promise<string | null>;
  createSocket: (url: string) => SocketLike;
  onState: (state: SocketState) => void;
  onOnline: (count: number) => void;
  onMessage: (message: CommunityMessage) => void;
  /** The server accepted our login. The place to catch up on what was missed while away. */
  onReady?: () => void;
};

export const PING_EVERY_MS = 25_000;
/** Nothing at all heard for this long: the connection is dead, even if the phone doesn't know. */
export const SILENCE_LIMIT_MS = 60_000;
/** The server must answer the auth frame within this long, or the attempt is given up. */
export const READY_TIMEOUT_MS = 20_000;
export const MAX_BACKOFF_MS = 30_000;

const CLOSE_UNAUTHORIZED = 4401;
const CLOSE_REPLACED = 4409;

/** 1 s, 2 s, 4 s … up to 30 s, spread ±25% so a server restart doesn't get 30 phones at once. */
export function backoffDelay(attempt: number, random: number): number {
  const base = Math.min(MAX_BACKOFF_MS, 1000 * 2 ** attempt);
  return Math.round(base * (0.75 + 0.5 * random));
}

/** `https://api.example.com` → `wss://api.example.com/community/ws`. */
export function socketUrl(apiUrl: string): string {
  return apiUrl.replace(/\/+$/, "").replace(/^http/, "ws") + "/community/ws";
}

export class CommunitySocket {
  private running = false;
  /** Bumped on every attempt and on stop(), so a late event from an old socket is ignored. */
  private generation = 0;
  private socket: SocketLike | null = null;
  private attempt = 0;
  private freshLoginTried = false;
  private lastHeard = 0;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private readyTimer: ReturnType<typeof setTimeout> | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly options: SocketOptions,
    private readonly random: () => number = Math.random,
  ) {}

  /** Connects, and keeps reconnecting until stop(). Calling it twice does nothing. */
  start(): void {
    if (this.running) return;
    this.running = true;
    this.attempt = 0;
    this.freshLoginTried = false;
    void this.connect();
  }

  /** Closes for good (screen left, app in the background). */
  stop(): void {
    if (!this.running) return;
    this.running = false;
    this.generation++;
    this.clearTimers();
    const socket = this.socket;
    this.socket = null;
    if (socket) this.detach(socket, 1000);
    this.options.onState("offline");
  }

  private async connect(): Promise<void> {
    const generation = ++this.generation;
    this.options.onState("connecting");
    let token: string | null = null;
    try {
      token = await this.options.getToken();
    } catch {
      token = null;
    }
    if (generation !== this.generation) return; // stopped or restarted while waiting
    if (!token) return this.scheduleRetry();

    let socket: SocketLike;
    try {
      socket = this.options.createSocket(this.options.url);
    } catch {
      return this.scheduleRetry();
    }
    this.socket = socket;
    this.lastHeard = Date.now();

    socket.onopen = () => {
      if (generation !== this.generation) return;
      try {
        socket.send(JSON.stringify({ type: "auth", token }));
      } catch {
        this.dropped(generation, 0);
      }
    };
    socket.onmessage = (event) => {
      if (generation !== this.generation) return;
      this.lastHeard = Date.now();
      this.handle(event.data);
    };
    socket.onclose = (event) => this.dropped(generation, event.code);
    // An error is always followed by a close; that is where it is handled.
    socket.onerror = () => {};

    this.readyTimer = setTimeout(() => this.dropped(generation, 0, true), READY_TIMEOUT_MS);
  }

  private handle(data: unknown): void {
    if (typeof data !== "string") return;
    let frame: { type?: unknown; online?: unknown; message?: unknown };
    try {
      frame = JSON.parse(data);
    } catch {
      return;
    }
    switch (frame.type) {
      case "ready":
        this.attempt = 0;
        this.freshLoginTried = false;
        if (this.readyTimer) clearTimeout(this.readyTimer);
        this.readyTimer = null;
        this.startPinging();
        if (typeof frame.online === "number") this.options.onOnline(frame.online);
        this.options.onState("live");
        this.options.onReady?.();
        break;
      case "presence":
        if (typeof frame.online === "number") this.options.onOnline(frame.online);
        break;
      case "message":
        if (frame.message && typeof frame.message === "object") {
          this.options.onMessage(frame.message as CommunityMessage);
        }
        break;
      // "pong" needs no action: hearing it is what matters (lastHeard).
    }
  }

  private startPinging(): void {
    if (this.pingTimer) clearInterval(this.pingTimer);
    this.pingTimer = setInterval(() => {
      const socket = this.socket;
      if (!socket) return;
      if (Date.now() - this.lastHeard > SILENCE_LIMIT_MS) {
        this.dropped(this.generation, 0, true);
        return;
      }
      try {
        socket.send(JSON.stringify({ type: "ping" }));
      } catch {
        this.dropped(this.generation, 0, true);
      }
    }, PING_EVERY_MS);
  }

  /** The connection ended (or was given up on). Close it properly, then decide when to retry. */
  private dropped(generation: number, code: number, closeIt = false): void {
    if (generation !== this.generation || !this.running) return;
    this.generation++; // nothing more from this socket counts
    this.clearTimers();
    const socket = this.socket;
    this.socket = null;
    if (socket) {
      if (closeIt) this.detach(socket, 4000);
      else this.detach(socket);
    }
    this.options.onState("offline");

    if (code === CLOSE_UNAUTHORIZED && !this.freshLoginTried) {
      // The login ran out. getToken() refreshes it, so try again straight away, once.
      this.freshLoginTried = true;
      void this.connect();
      return;
    }
    // Someone else (the same account on a 4th place) took this slot: don't fight over it.
    this.scheduleRetry(code === CLOSE_REPLACED ? MAX_BACKOFF_MS : undefined);
  }

  private scheduleRetry(delay?: number): void {
    if (!this.running) return;
    this.options.onState("offline");
    const wait = delay ?? backoffDelay(this.attempt, this.random());
    this.attempt++;
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      if (this.running) void this.connect();
    }, wait);
  }

  private detach(socket: SocketLike, code?: number): void {
    socket.onopen = socket.onmessage = socket.onclose = null;
    socket.onerror = () => {};
    try {
      socket.close(code);
    } catch {
      // already closed
    }
  }

  private clearTimers(): void {
    if (this.pingTimer) clearInterval(this.pingTimer);
    if (this.readyTimer) clearTimeout(this.readyTimer);
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.pingTimer = this.readyTimer = this.retryTimer = null;
  }
}
