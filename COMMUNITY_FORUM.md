# Community forum: status and hand-off

> **FINISHED on 2026-11-12 (snapshot `.phase-snapshots/10`, tag `community-forum`).** Every step in
> sections 5 to 7 was done: the app screens, the keyboard fixes, the tests, README, privacy, trial
> checklist, OPEN_QUESTIONS.md and the ROADMAP.md progress log. What remains is the user's: phone
> testing, accounts for 30 people, moderator emails on Render (OPEN_QUESTIONS.md, last section).
> **This file is now only history and can be deleted**; its content lives in README.md, docs/,
> OPEN_QUESTIONS.md and ROADMAP.md. Sections 2 and 5 to 7 below describe the state BEFORE the app
> work and are out of date.

**Read this whole file before touching the feature.** It is the brief for whoever continues the
work (a new Claude Code session has none of the context this was written with). Delete the file
when the feature is finished and its content has moved into README.md, docs/ and
OPEN_QUESTIONS.md (step 7 below).

Last updated: 2026-11-12. State saved as snapshot `.phase-snapshots/09`.

## 1. What was asked

The user's request, 2026-11-12, in short:

- A new feature called **Community forum**: one group chat where everyone who has access to the
  app can ask questions and answer each other.
- **Text only.** No pictures or videos (no storage for them). Audio "maybe, if it is easy to
  manage".
- **About 30 people must be able to talk at the same time without issues or errors.**
- **Fix keyboard problems**: the keyboard covering or overlapping the input, and similar.

The user then paused the work and asked for it to be saved with instructions for the next
session. Nothing below has been reviewed by the user yet.

## 2. Where it stands

| Part | State |
|---|---|
| Backend (`backend/app/community/`, migration, settings, tests) | **Done and verified** |
| Typed API client in the app (`app/src/api/openapi.json`, `schema.d.ts`) | **Regenerated**, includes the community endpoints |
| App: chat screen, sync, socket client, name form, entry point | **Not started** (no file exists yet) |
| Keyboard fixes (chat screen and the existing screens) | **Not started**; findings so far in section 6 |
| App tests for the new pure modules | **Not started** |
| README, docs/privacy.md, docs/v1-trial.md, OPEN_QUESTIONS.md, ROADMAP.md | **Not updated** |
| Memory file `local-dev-setup.md` | Not updated for this feature (a pointer memory to this file exists) |

Verified on 2026-11-12, after the backend was finished:

- Backend: `pytest` 527 passed (485 before, 42 new), `ruff check`, `ruff format --check`,
  `mypy app tests` clean, `alembic check` reports no difference between models and migrations.
- App: `npm run typecheck` clean and `npm test` 41 passed with the regenerated client. `npm run
  lint` and the Android bundle export were not re-run (no app code changed).
- Nothing has run on a phone. No emulator or `adb` exists on this Mac.

## 3. Decisions already made (keep them unless the user says otherwise)

The user's standing instruction is: pick the sensible default, record it as an open question,
keep going (memory `open-questions-log`). These were picked:

1. **One room**, not channels. Replies quote the message they answer (`reply_to_id`), which is
   what makes questions and answers readable when 30 people talk at once.
2. **Display names.** Emails are never shown to other people. A person chooses a name (2 to 24
   characters, unique whatever the case or accents) before the first post. Reading needs no name.
3. **Live delivery = WebSocket on the FastAPI server, plus a timed "anything new?" request.**
   The socket only pushes; posting and deleting are ordinary HTTP requests. This needs no new
   service and no worker, so it stays inside the $0 stack. Supabase Realtime was rejected: every
   table has row-level security with no policies (the public Data API is blocked on purpose),
   and it can't be tested against the local Postgres.
4. **Voice messages are NOT built.** It is not "easy to manage": it needs file storage, a
   recording permission (the microphone is deliberately blocked in `app/app.json`), upload,
   playback and a way to moderate audio. Record it as an open question (step 7).
5. **Deleting.** Anyone can delete their own message; the text is erased from the database and
   everyone sees "message deleted". Moderators (emails in `COMMUNITY_MODERATOR_EMAILS`) can
   delete anyone's. No editing.
6. **Posting limit:** 20 messages a minute per person (`COMMUNITY_MESSAGES_PER_MINUTE`), 2,000
   characters per message.
7. **Navigation:** a stack screen at `/community`, opened from a card on the Today screen. Not a
   seventh tab (the tab bar is full, see `app/src/app/(app)/(tabs)/_layout.tsx`), and a stack
   screen has no tab bar under the input, which keeps the keyboard handling simple.
8. **Not built, to be listed as open:** unread badge, push notifications for new messages,
   typing indicators, report/block, editing, message search, pruning old messages.

## 4. The backend as built

### Files

| File | What it holds |
|---|---|
| `backend/app/community/models.py` | `CommunityProfile` (name per user), `CommunityMessage`, the `community_change_seq` sequence |
| `backend/app/community/schemas.py` | Request and response models, `clean_body`, `clean_name`, `name_key`, the limits |
| `backend/app/community/service.py` | All reads and writes. **Read its module docstring**: it explains the write lock |
| `backend/app/community/hub.py` | In-memory list of connected phones, per-connection queues, close codes |
| `backend/app/community/router.py` | The HTTP endpoints and the `/community/ws` socket |
| `backend/migrations/versions/20261112_5b7e1c9a4f20_community_forum.py` | Tables, sequence, row-level security |
| `backend/app/core/auth.py` | `verify_token()` was split out of `get_current_user` so the socket can check a token |
| `backend/app/core/config.py` | `community_messages_per_minute`, `community_moderator_emails`, `community_max_connections` |
| `backend/Dockerfile` | `--ws-max-size 16384`, and a comment: one process only |
| `backend/.env.example`, `render.yaml` | The new settings |
| `backend/tests/test_community_api.py` | Names, posting, retries, paging, changes, delete, replies, limits |
| `backend/tests/test_community_socket.py` | Socket sign-in, pushes, presence, and the hub (slow phone, too many phones) |
| `backend/tests/test_community_load.py` | 30 people posting at once against a real uvicorn server |

### HTTP API (all need the usual `Authorization: Bearer` token)

| Call | Does |
|---|---|
| `GET /community/me` | `{user_id, display_name (null until chosen), moderator, max_message_chars, messages_per_minute}` |
| `PUT /community/me` `{display_name}` | Sets the name. 409 "Someone already uses that name", 422 for a bad name |
| `GET /community/messages?before=<seq>&limit=50` | Latest page, or the page before `before`. Oldest first. `{items, has_more, rev}` |
| `GET /community/changes?after=<rev>&limit=200` | Everything posted **or deleted** since `after`, ordered by `rev`. `{items, rev, has_more}` |
| `POST /community/messages` `{id, body, reply_to_id?}` | Posts. The phone makes up `id` (a UUID); sending the same id again returns the saved message, posts nothing. 409 no name yet, 429 too fast (`Retry-After: 15`), 404 reply target gone, 422 bad text |
| `DELETE /community/messages/{id}` | Returns the message as deleted (`body: null, deleted: true`). 403 not yours, 404 unknown. Doing it twice is fine |

A message: `{id, seq, rev, author_id, author_name, body|null, deleted, reply_to: {id,
author_name, excerpt|null}|null, created_at}`. `seq` is its place in the conversation (sort by
it). `rev` goes up when the message changes (today: when deleted).

### The socket: `WS /community/ws`

- The phone's first frame must be `{"type":"auth","token":"<Supabase access token>"}` within 15
  seconds. (No header, no token in the URL.)
- The server answers `{"type":"ready","online":N}`, then pushes
  `{"type":"message","message":{...}}` for every new **and** deleted message (same shape as the
  API; treat it as "insert or replace by id") and `{"type":"presence","online":N}` when the
  number of people changes.
- The phone sends `{"type":"ping"}`; the server answers `{"type":"pong"}`. A phone silent for 80
  seconds is closed. Anything else the phone sends is ignored.
- Close codes: `4400` bad first frame, `4401` no or expired login (also sent when the token
  expires mid-connection: reconnect with a fresh token), `4408` idle, `4409` same person on more
  than 3 connections (oldest is closed), `4429` the phone wasn't reading fast enough (reconnect
  and catch up), `1013` full or sign-in service unreachable (retry later).

### What is guaranteed, and why

- **"Everything after `rev` N" never misses a message.** Every write takes a transaction-level
  advisory lock before it takes its number, so numbers are committed in order. Without the lock,
  two people posting at once can commit out of order and a phone would lose a message for good.
  Do not remove the lock or move the insert before it.
- **A slow phone can't slow the others.** Each connection has a bounded queue (200 events);
  `Hub.publish` never waits; a full queue drops that one connection with `4429`.
- **One server process only.** The hub is in memory. The Dockerfile starts one process and
  Render's free plan runs one. With more than one, pushes would only reach the phones on the same
  process; nothing would be lost (the timed request catches up) but it would arrive late.

### Measured (this Mac, local Postgres, server in its own process)

- 30 people each posting about once a second (20 messages a second in total, far more than a real
  chat): a send took 14 ms at the median and 21 ms at the 95th percentile, and the message was on
  the other 29 phones 1 ms later. All 9,000 deliveries arrived, once each, in order.
- 30 people posting as fast as they can: about 32 messages a second, 95% of sends under 0.5 s.
- These are local numbers. Production adds the network between Render and Supabase and Render's
  much slower free CPU; it has not been measured there.

### Running the backend checks (see memory `local-dev-setup` for why)

```sh
cd backend
ENVIRONMENT=test SUPABASE_URL=https://test-project.supabase.co \
TEST_DATABASE_URL=postgresql+psycopg://mac@localhost:5432/lumen_test \
DATABASE_URL=postgresql+psycopg://mac@localhost:5432/lumen_test \
.venv/bin/python -m pytest -q
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app tests
```

`uv` is not on PATH; the env vars must be on the same command line or the database tests
silently skip. `pytest tests/test_community_load.py -s` prints the timing of the 30-person run.

## 5. What is left: the app

Follow `app/AGENTS.md` (Expo 58: read the versioned docs before using an Expo or React Native
API, run lint and typecheck before calling anything done). Match the existing code: features in
`app/src/features/<name>/`, screens in `app/src/app/(app)/`, shared UI in `app/src/ui/`, colours
and spacing from `app/src/ui/theme.ts`, server calls through `api` + `unwrap`
(`app/src/features/capture/api.ts` is a good model). No new dependency is needed: `expo-crypto`
(`randomUUID`) and `react-native-safe-area-context` are already installed; React Native has
`WebSocket` built in.

### Step 1. `app/src/features/community/store.ts` (pure, no React Native imports, so `npm test` can run it)

Holds the conversation and decides what is shown. Suggested shape:

- State: confirmed messages by id, a list of pending (not yet confirmed) sends, `oldestSeq`,
  `hasOlder`, and `cursor` (the `rev` to ask changes after).
- `applyPage(page)`: first load and "load older". Sets `cursor` from the first page's `rev`.
- `applyChanges(result)`: insert or replace each item, then `cursor = result.rev`.
- `applyEvent(message)`: a socket push. Insert or replace by id, keeping the copy with the higher
  `rev`. **It must not move `cursor`.** The cursor only moves on answers from `GET
  /community/changes`; that is what makes the timed request a real safety net whatever the socket
  delivered or dropped.
- Ignore a changed message that is older than `oldestSeq` and not already loaded (a deletion far
  up the history).
- Pending sends: `addPending({id, body, replyTo})`, `markFailed(id, reason)`, `retry(id)`. A
  pending send disappears as soon as a confirmed message with the same id exists (the socket
  echo often arrives before the POST answers).
- `visible()`: confirmed messages by `seq`, then pending ones in the order they were written.
- For the quoted message in a reply, prefer the local copy of the target (so a deleted target
  shows as deleted), fall back to `reply_to` from the server.

### Step 2. `app/src/features/community/socket.ts` (reconnecting client; inject `WebSocket` and timers so it can be tested)

- URL: `env.apiUrl` with `http` replaced by `ws` at the start (so `https` becomes `wss`), plus
  `/community/ws`.
- On open: get the token with `supabase.auth.getSession()` and send the auth frame. Count as
  connected only after `ready`.
- Ping every 25 s. If nothing at all arrives for 60 s, close and reconnect.
- Reconnect with backoff (1 s, 2 s, 4 s … up to 30 s, with some randomness); reset on `ready`.
  On `4401`, reconnect at once the first time (the token is refreshed by `getSession`), then
  back off.
- Connect only while the chat screen is focused and the app is in the foreground (`AppState`).
  Close on blur, background and unmount.
- Surfaces: state (`connecting` / `live` / `offline`), `online` count, `onMessage`.

### Step 3. `app/src/features/community/api.ts` and `useCommunity.ts`

- `api.ts`: types from `components["schemas"]` (`CommunityMessageOut` etc.), `useCommunityMe()`,
  `useSetCommunityName()`, and plain functions for page, changes, post and delete.
- `useCommunity.ts`: wires store + socket + sync.
  - Sync = `GET /community/changes?after=cursor`, one at a time (if asked again while one is
    running, run once more afterwards). If the answer has `has_more`, the phone is too far
    behind: drop the state and load the latest page again.
  - When to sync: on socket `ready`, when the app returns to the foreground, every ~25 s while
    the socket is live, every ~4 s while it is not.
  - Send: make the id with `randomUUID()`, add it as pending, POST. On success insert the
    answer. On no connection, timeout, 5xx or 429: mark it "Not sent. Tap to try again" and
    retry **with the same id**. 409 "Choose a name" opens the name form; 404 and 422 show the
    server's message.
  - Do not add these queries to the persisted cache (`app/src/app/_layout.tsx` persists only
    `reviews` and `dashboard`); the chat is not kept on the phone, so sign-out has nothing to
    clear.

### Step 4. The screen: `app/src/app/(app)/community/index.tsx`

- Register it in `app/src/app/(app)/_layout.tsx`:
  `<Stack.Screen name="community/index" options={{ title: "Community" }} />`.
- An **inverted `FlatList`** (newest first in the data). The newest message then stays just above
  the input when the keyboard opens, and older messages load with `onEndReached` using
  `before=oldestSeq`.
- When the reader has scrolled up, new messages must not move what they are reading: use
  `maintainVisibleContentPosition` and show a "New messages" button that jumps to the bottom.
  (Check both against the React Native 0.88 docs first.)
- Each message: author name (a steady colour per `author_id`), time, text, the quoted message if
  it is a reply, "message deleted" for deleted ones, day separators. Own messages on the right.
  Pending ones dimmed; failed ones with "Not sent. Tap to try again".
- Long press: Reply, Copy, and Delete when `author_id === me.user_id || me.moderator` (confirm
  with `Alert`, as `capture/index.tsx` does).
- Under the title or above the list: "N here now", "Connecting…", or "No connection. Messages
  will arrive when you are back online."
- Input: multiline, grows to about five lines, `maxLength` from `me.max_message_chars`, a
  counter near the limit, a Send button that is disabled while empty, a "Replying to …" strip
  with a cancel. Sending must not close the keyboard.
- With no display name yet: show the name form where the input would be. Also reachable later
  ("Change name" in the header).
- Accessibility as elsewhere in the app: labels on buttons, errors via `ErrorText`.

### Step 5. Entry point

A card on the Today screen (`app/src/app/(app)/(tabs)/index.tsx`), next to "Class tasks" and
"Stuck on an exercise?": title "Community", one line of explanation, link "Open the community
chat" → `router.push("/community")`.

## 6. What is left: keyboard

Facts read from the Expo docs on 2026-11-12 (guides/keyboard-handling and the SDK 58 pages):

- Expo apps on Android are edge to edge: **the window does not resize for the keyboard**. A view
  with no handling stays under it.
- Recommended: `KeyboardAvoidingView` with `behavior="padding"` on both platforms, and
  `useHeaderHeight()` from `expo-router/react-navigation` as `keyboardVerticalOffset` when there
  is a header (the value includes the status bar).
- Never set `android.softwareKeyboardLayoutMode` to `pan` together with `behavior="padding"`: the
  input moves up twice. It is unset here (default `resize`); leave it.
- For tabs the guide suggests `tabBarHideOnKeyboard: true`. Not set here today.
- `react-native-keyboard-controller` gives smoother, frame-by-frame movement but needs
  `react-native-reanimated` as a real dependency, a provider at the root and a development build.
  Not used; `KeyboardAvoidingView` is the project's choice (`app/src/ui/FormScroll.tsx`). Don't
  add it without the user asking.

What exists: `AvoidKeyboard` and `FormScroll` in `app/src/ui/FormScroll.tsx`, used by every
form screen. Never seen on a phone.

To do:

1. **Chat screen.** Wrap list + input in `AvoidKeyboard`. Add the bottom safe-area inset
   (`useSafeAreaInsets().bottom`) under the input **only while the keyboard is hidden** (track it
   with `Keyboard.addListener("keyboardDidShow" / "keyboardDidHide")`); otherwise a gap the height
   of the navigation bar appears above the keyboard. `keyboardShouldPersistTaps="handled"` on the
   list so tapping Send or a message doesn't just close the keyboard.
2. **`app/src/app/(app)/(tabs)/words.tsx`**: a search field above a `FlatList`, with no keyboard
   handling. With the keyboard open the last rows can't be scrolled into view. Wrap in
   `AvoidKeyboard` and add `keyboardShouldPersistTaps="handled"`.
3. **Bottom edge on stack screens.** Nothing in `app/src` uses safe-area insets, so on screens
   without a tab bar the last button of a scrolling form can sit under Android's navigation bar.
   Consider adding the bottom inset to the scroll content inside `FormScroll` (one place fixes
   every form). Check it doesn't double up inside the tabs, where the tab bar already covers
   that area.
4. Go through every screen with an input (list: `grep -rl "TextInput\|Field" app/src`) and
   confirm each is inside `FormScroll` or `AvoidKeyboard`. Checked so far: `write.tsx`,
   `review/session.tsx`, `player/[id].tsx` and `sign-in.tsx` are; `words.tsx` is not.
5. `KeyboardAvoidingView` on Android moves only after the keyboard has finished opening
   (`keyboardDidShow`), so the input jumps rather than slides. That is expected with this
   component; say so rather than calling it a bug.

None of this can be confirmed without a phone. Say that plainly in the summary, and add the
checks to `docs/v1-trial.md`.

## 7. What is left: tests, docs, wrap-up

1. **App tests** (`app/tests/*.test.ts`, `node:test` via `npm test`): the store (merge by id and
   `rev`, cursor only moves on changes, pending → confirmed, failed → retry keeps the id, order)
   and the socket client (auth frame first, ping, reconnect and backoff, `4401`), with a fake
   `WebSocket` and fake timers.
2. **App checks:** `cd app && npm run typecheck && npm run lint && npm test`, then
   `npx expo-doctor` and `npx expo export --platform android --output-dir <scratch dir>`.
3. **README.md:** a "Community forum" section (what it is, text only, names, deleting,
   moderators via `COMMUNITY_MODERATOR_EMAILS`). The README's opening line calls the app "a
   personal study companion"; the forum is the first shared feature, so adjust the wording, and
   note that every other table stays private to its owner.
4. **docs/privacy.md:** messages are stored as written and every signed-in person can read them;
   only the display name is shown, never the email; deleting erases the text; the nightly backup
   includes messages.
5. **docs/v1-trial.md:** phone checks: two phones chatting, keyboard on the chat and on the
   forms, airplane mode on and off (pending → sent), app left in the background for an hour then
   reopened.
6. **OPEN_QUESTIONS.md:** add a "Community forum" section and a row in the table at the top.
   - Decide: voice messages (not built, why); one room vs channels; who the moderators are;
     limits (20 a minute, 2,000 characters); no editing; no unread badge or notifications; how
     long messages are kept (forever today); report or block.
   - Decide, important: **how 30 people get accounts.** Sign-up is invite-only (README, setup
     step 2) and the app has no sign-up screen, so today each account is made by hand in the
     Supabase dashboard.
   - Check: the AI limits were sized for one learner. Per-person limits still hold, but the
     shared daily ceilings (Groq 800 requests a day) are now shared by everyone.
   - Check: the database pool is 5 connections (`backend/app/core/database.py`), fine for the
     chat in the load test, untested for 30 people using the whole app at once.
   - Check: Render's free server sleeps after about 15 quiet minutes and has little CPU; whether
     an open chat socket keeps it awake is unknown.
   - Do: set `COMMUNITY_MODERATOR_EMAILS` on Render; test on two phones.
7. **ROADMAP.md** progress log: an entry for this work (what changed, why, what was verified).
8. **Snapshot:** no git here. Save each finished unit as `.phase-snapshots/10`, `11`, … exactly
   like `09` (rsync of the project without `node_modules`, `.venv`, caches, `.expo`,
   `.phase-snapshots` and any real `.env`, plus `message.txt`; `tag.txt` on the last one, e.g.
   `community-forum`).
9. **Memory:** update `local-dev-setup.md` with a line for this feature and remove the
   `community-forum-handoff` memory and this file once everything above is done.
10. Tell the user plainly what was not tested (anything on a phone, anything on Render).

## 8. Things learned the hard way in this session

- In the socket handler, clean up the two tasks with `asyncio.wait`, not `asyncio.gather`:
  `gather` swaps the cancellation it is given for its children's, and Starlette's test client
  then fails with a bare `CancelledError` when a socket closes.
- SQLAlchemy 2.1 here: `Row._tuple()` is deprecated, and `Select[...]`/`Row[...]` take the
  column types directly (`Select[A, str]`, not `Select[tuple[A, str]]`).
- Postgres refuses text containing a NUL character; `clean_body` and `clean_name` strip control
  and invisible characters for that reason. Keep new text fields behind them.
- New API schema names must not collide with existing ones or the generated client renames both
  (`MeOut` already exists, hence `CommunityMeOut`).
- Regenerate the client after any endpoint change (needs no `uv`):
  `cd backend && ENVIRONMENT=test SUPABASE_URL=https://test-project.supabase.co DATABASE_URL=postgresql+psycopg://u:p@localhost:5432/unused .venv/bin/python -m app.export_openapi > ../app/src/api/openapi.json && cd ../app && npx -y openapi-typescript@7.13.0 src/api/openapi.json -o src/api/schema.d.ts`
- The load test runs the server in a thread of the test process, so client and server share one
  CPU core there; its printed time is pessimistic. The numbers in section 4 came from running the
  server as a separate process.
