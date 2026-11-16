# Roadmap: making Lumen A1 reliable, accurate and ready to use

This is the improvement roadmap for the app as it stood on 2026-11-11, after all 13 build phases. The original build roadmap (what each feature is and how it was built) now lives in [docs/build-history.md](docs/build-history.md).

**If you are picking this work up again:** read the [Progress log](#5-progress-log) at the bottom first. It says what is done, what was verified and what is next.

## 1. Product understanding

Lumen A1 is a personal study companion for one learner taking a German A1 course (Netzwerk neu, tests at ASH, then the Goethe A1 exam). It runs on an Android phone, costs nothing to run, and must stay useful when the AI is unavailable.

| Part | What it is |
|---|---|
| `app/` | Expo SDK 58 / React Native 0.88 app (Expo Router, TanStack Query). Android only, installed as an APK. |
| `backend/` | One FastAPI service (Python 3.13, SQLAlchemy async, Alembic). Hosted on Render's free plan. |
| Database and login | Supabase free plan: Postgres for data, Supabase Auth for sign-in. The app signs in with Supabase and sends the login token to the backend, which verifies it. |
| AI | Groq and Gemini, called only by the backend through one gateway (`backend/app/ai`) with a cache, per-learner daily limits and provider fallback. |
| Grammar checking | LanguageTool's free public API plus our own dictionary-backed rules (`backend/app/coach`). |
| Text recognition | Google ML Kit on the phone (`expo-text-extractor`). Photos never leave the phone. |

The main flows:

1. **Today** (home): what to do today and why, built from due reviews, weak grammar, homework and the next test.
2. **Words**: type a word, the Wiktionary import fills in article, plural, verb forms and audio.
3. **Review**: FSRS-scheduled cards (recall, produce, article and plural, sentence, mistake retry). Answers are saved on the phone first and uploaded in order, so reviewing works offline.
4. **Write** (sentence coach): LanguageTool finds errors, our rules confirm them against the dictionary, the AI explains and adds what LanguageTool missed. Each correction is labelled Confirmed, Likely or Uncertain. Accepted corrections go to the mistake log and become retry cards.
5. **Scan an exercise**: photo, on-phone text recognition, the learner corrects the text, the AI gives hints and answers, and each answer is checked by LanguageTool and the dictionary.
6. **Class tasks**: paste or share a WhatsApp message, the AI proposes tasks, our own code works out the dates, the learner approves, the phone schedules reminders.
7. **Course map, grammar tracker, mistake log, tests and readiness, Allango player.**

## 2. What works well and is left alone

- **The trust model.** The AI never decides alone: only the dictionary and LanguageTool can make something "Confirmed", dates are computed by our code, and every AI answer is validated against a schema. This is the right design for a learner and stays.
- **The AI gateway's budget, cache and throttle** (`ai/budget.py`, the cache in `ai/gateway.py`). Tested against real Postgres, correct under concurrency.
- **The review engine**: FSRS scheduling, stage rules, idempotent uploads with client-made ids.
- **The date parser** for class messages (`capture/dates.py`), the redaction of personal details, and the privacy posture (Sentry scrubbed, nothing personal stored).
- **The database design**: every table has row-level security on, ownership checks on every query, sensible indexes for a single learner's data. No schema change is needed for correctness.
- **Backup with nightly restore check**, the Render and EAS setup, and the docs in `docs/`.
- **The typed API client** generated from the backend's OpenAPI schema.
- **The visual design**: plain cards, one accent colour, text-first. Kept as it is.

## 3. Findings, ranked by impact on the learner

Each finding was verified, not assumed. "Live" means checked against the real service on 2026-11-11 with the keys in `backend/.env`.

### Blocks a feature outright

1. **The Groq fallback model no longer exists (live).** The default `llama-3.1-8b-instant` returns `404 model_not_found`. Every AI request that reaches Groq fails.
2. **The Gemini key cannot be used (live).** Every call returns `402: Your prepayment credits are depleted`. The key belongs to a project on prepaid billing with no credit, not the free tier. With finding 1, **no AI feature works at all today**: the sentence coach has no explanations, and the exercise scanner and class-task scan return "AI unavailable". Needs you (see section 6); the code must cope either way.
3. **The replacement Groq models are reasoning models, and the current request shape breaks on them (live).** `openai/gpt-oss-120b` spent 315 of 388 output tokens thinking and then ran out of room; Groq answers that with HTTP 400, which the gateway treats as an outage and benches the provider for 30 seconds.
4. **`GROQ_BACKUP_API_KEY` in `backend/.env` is silently ignored.** No code reads it.

### Loses the learner's work

5. **Offline review answers are thrown away on any 4xx response.** The outbox drops an answer when the server says 401 (sign-in token could not be refreshed), and the server returns 401 whenever it cannot reach Supabase's key endpoint, so a Supabase hiccup deletes every queued answer.
6. **A phone with a wrong clock loses every review.** The server rejects answers timestamped in the future (or more than 7 days old) with 422, and the app then drops them.

### Gives wrong or confusing German feedback

7. **"No errors found." is shown above a correction (live).** The coach prompt asks for the explanation of LanguageTool's findings separately from the AI's own issues, so when only the AI finds the error both models tested wrote "No errors found." next to a real correction.
8. **The AI's word-order fixes can corrupt the suggested text (live).** For "Ich aufstehe um 6 Uhr" the model returned `aufstehe -> stehe ... auf`; applied literally this gives "Ich stehe ... auf um 6 Uhr."
9. **AI-only corrections are never checked.** They are always labelled "Likely", even when the corrected sentence itself has an error LanguageTool would catch.
10. **Exercise answers are not checked against the exercise.** Nothing verifies that the answer is in the filled-in sentence, that the sentence is still the one printed, or that the hint doesn't give the answer away.
11. **Umlauts and ß get no useful feedback in reviews.** Typing "Madchen" or "Maedchen" for "Mädchen", or "Strasse" for "Straße", is just "wrong" with no hint why. Comparison also assumes both sides use the same Unicode form.
12. **Text read from photos is passed on raw.** Lost gaps (`_ _ _`, `.....`), words split across lines (`Früh-` / `stück`), `ß` read as `B` (`heiBe`) and `Ich` read as `lch` all reach the learner uncorrected, and a badly read photo gets no warning.

### Makes failures hard to understand or recover from

13. **The test suite reads the developer's real `backend/.env`.** One test fails today because of it, and a test that forgets to fake the providers would call the real AI with real keys.
14. **A provider with a bad key or dead model is retried every 30 seconds for ever**, adding a failed round trip to every AI request, and one bad answer from the first provider ends the request instead of trying the next.
15. **Configuration mistakes fail obscurely.** An empty `SUPABASE_URL` or a `DATABASE_URL` with the wrong prefix is accepted at start-up and fails later with an unrelated error. The app throws while loading if a build value is missing, which in a release build is a blank screen. `backend/.env` holds only the AI keys, so the backend cannot start from it.
16. **A paused Supabase project or a database outage shows as a generic "server had a problem".** The learner (and you) can't tell it from a bug.
17. **`GET /coach/checks` runs up to 41 queries** for 20 checks (one for each check's corrections and task).

### Polish (lowest priority)

18. Text inputs have no accessibility label, error messages are not announced to screen readers, and the sign-in screen ignores the shared theme.
19. On Android the keyboard can cover the field being typed in on long forms (to be confirmed on a phone).

### Could not be done here

20. **Git commits.** This machine's guard hook allows only read-only git commands, so I could not create the branch, commits or tags. Each unit of work is saved as a snapshot instead, and one script turns them into the branch with a commit per unit and a tag per phase (section 6).
21. **No Android SDK or phone here.** Nothing native could be built or run. Everything is checked as far as type-checking, linting, unit tests and an Android bundle can go.

## 4. The plan

Three phases. Each leaves the app working and better than before.

### Phase 1: Reliability and correctness

Goal: nothing the learner does is lost, AI features work again, and failures say what is wrong.

- [x] 1.1 Tests never read the real `.env` (fixes the failing test; real keys can't be used by tests).
- [x] 1.2 AI gateway works with today's models: new Groq default (`openai/gpt-oss-120b`, chosen by live test), reasoning settings, the backup key as a third provider, ceilings matched to the real limits.
- [x] 1.3 AI gateway fails over properly: a bad answer tries the next provider; Groq's JSON-mode 400 counts as a bad answer, not an outage; a bad key, missing credit or dead model benches the provider for 10 minutes with one clear log line.
- [x] 1.4 Offline answers are never dropped for the wrong reason: the app keeps them on 401/403/408/429/5xx; the server puts an out-of-range timestamp back in range instead of rejecting the answer.
- [x] 1.5 A Supabase or database outage answers 503 with a plain message, never 401 or 500.
- [x] 1.6 Configuration: validated at start-up with clear messages; `backend/.env` and `app/.env` completed with every variable; both `.env.example` files document each one; the app shows a "this build is not configured" screen instead of crashing; `render.yaml` lists the new variables.
- [x] 1.7 `GET /coach/checks` uses 3 queries whatever the number of checks.

**Done when**

- [x] `pytest` passes with the real `backend/.env` present, and with outbound HTTP blocked (no test reaches a real service).
- [x] A live call through the real gateway returns a valid sentence-coach answer from Groq.
- [x] Tests prove: bad output falls through to the next provider; a 402/404 benches the provider; a 401 from the server keeps the outbox; a future timestamp is accepted and clamped; a JWKS outage is 503.
- [x] Backend: ruff, mypy and pytest clean. App: typecheck, lint and tests clean.

### Phase 2: AI and OCR accuracy for German

Goal: what the app says about German is right more often, and says so honestly when unsure.

- [x] 2.1 Coach prompt rewritten and measured on a fixed set of A1 sentences (verb position, `kein`/`nicht`, modal verbs, separable verbs, dative, accusative, verb endings, and correct sentences that must not be "corrected"). The test set is kept in the repo (`python -m app.ai.evaluate`) so the next model change can be measured the same way.
- [x] 2.2 AI corrections are verified: unusable ones are dropped (ellipsis, not found in the text, no real change); each corrected sentence is re-checked with LanguageTool and marked Uncertain if it objects; "No errors found." can never sit next to a correction.
- [x] 2.3 Exercise answers are verified: the answer must appear in the filled-in sentence and the sentence must match the printed line; a hint that contains the answer is replaced; anything that fails is marked Uncertain.
- [x] 2.4 Review grading understands umlauts and ß: exact spelling is still required, but "Maedchen", "Madchen" and "Strasse" get a specific tip; both sides are compared in the same Unicode form. Server and app rules stay identical.
- [x] 2.5 Text from photos is cleaned up before the learner sees it (gaps, split words, `ß`/`B`, `lch`/`Ich`, Unicode form), and a poorly read photo gets a clear warning with what to do. On-device vs cloud reading is decided and written down.

**Done when**

- [x] The live evaluation scores at least 15 of 16 on the coach set (the set grew from 12 to 16 sentences while the prompt was being worked on), with no correction on any correct sentence. Result: 16 of 16.
- [x] Unit tests cover AI response parsing and verification, OCR clean-up and the umlaut feedback (server and app).
- [x] All checks clean.

### Phase 3: Production readiness and UX

Goal: the release build is as checked as it can be without a phone, and the rough edges are gone.

- [x] 3.1 Release configuration checked: `expo-doctor`, an Android production bundle, and the generated Android manifest (permissions, backup flag, share target).
- [x] 3.2 Keyboard no longer covers inputs on long forms (Android). Done in code from Expo's current guidance; to be confirmed on a phone.
- [x] 3.3 Accessibility: labelled inputs, announced errors, sign-in screen on the shared theme.
- [x] 3.4 Docs brought up to date (README, INSTALL, privacy, `.env.example`), and this file finished with the summary, the device test steps and the values to fill in.

**Done when**

- [x] `expo-doctor` reports no problems, or each one is explained here. (20 of 20 checks pass.)
- [x] The Android bundle builds with production settings.
- [x] All checks clean; the final section of this file is complete.

## 5. Progress log

Newest last. Each entry: what changed, why, what was verified.

### 2026-11-11: exploration and baseline

- Read the whole codebase (backend modules, migrations, tests, app screens and features, config, CI, docs).
- Baseline: backend 403 passed, **1 failed** (`test_providers_without_a_key_are_left_out_and_typos_are_rejected`, caused by the real `.env`); app typecheck, lint and 19 tests clean.
- Live checks with the real keys (model lists and 4 to 14 test prompts per model): Groq `llama-3.1-8b-instant` is gone; Gemini answers 402 on every model; `openai/gpt-oss-120b` with low reasoning effort and extra token room answered 14 of 14 prompts with valid output and judged all 12 test sentences correctly in about 1 second each; `qwen/qwen3.8-27b` is faster but is limited to 1,000 output tokens a minute on the free plan and gave two muddled explanations; strict JSON-schema mode on Groq works but adds about 200 input tokens per call against an 8,000 tokens-a-minute limit, so plain JSON mode plus our own schema validation stays.
- Groq's limits for `openai/gpt-oss-120b`, read from its response headers: 1,000 requests a day and 8,000 tokens a minute per key. The two Groq keys have separate counters.
- Git is blocked for me (finding 20). Snapshots go to `.phase-snapshots/` (git-ignored).
- Decision: the old `ROADMAP.md` moved to `docs/build-history.md` so this file can be the roadmap you asked for.

### 2026-11-11: Phase 1 done (reliability and correctness)

What changed and why:

- **Tests are cut off from the real `.env`** (`core/config.py`: no env file under `ENVIRONMENT=test`). The failing test passes, and a test can no longer spend real AI quota.
- **AI works again, through Groq.** New default `GROQ_MODEL=openai/gpt-oss-120b` with `GROQ_REASONING_EFFORT=low`; the request leaves the model 600 tokens of room to think (`ai/providers.py`). `GROQ_BACKUP_API_KEY` is now read and is a provider of its own (`groq_backup`), counted separately. Default order is `groq,groq_backup,gemini`: Groq first because it is the one verified live. Ceilings set from Groq's real limits (800 of 1,000 requests a day per key).
- **Fail-over is right.** An answer that is cut off, not JSON or the wrong shape now tries the next provider (`ai/gateway.py`). Groq's `json_validate_failed` (HTTP 400) is a bad answer, not an outage. HTTP 401, 402, 403 and 404 mean a broken setting: one clear error log that says which, and the provider is left alone for 10 minutes instead of 30 seconds.
- **Review answers are not lost.** The app keeps a queued answer on 401, 403, 408, 429 and 5xx and only drops it on 404, 409 or 422 (`app/src/api/errors.ts: keepForRetry`). The server accepts an answer whose timestamp is in the future or more than 60 days old and counts it as given now, instead of refusing it (`review/router.py`); up to 60 days offline keeps its real time.
- **Outages say what they are.** Supabase's key endpoint unreachable is 503, not 401 (`core/auth.py`, with a 10-second limit instead of the library's 30). A dropped database connection, a paused Supabase project or a full pool is 503 with a message that names Supabase, still reported to Sentry (`main.py`).
- **Configuration.** `SUPABASE_URL`, `DATABASE_URL` and `GROQ_REASONING_EFFORT` are validated at start-up with a message that says where to get the value. `backend/.env` now lists every required variable (your three keys were kept; the old file is saved as `backend/.env.before-2026-11-11`). `app/.env` was created; the app reads `.env`, not `.env.local`. Both `.env.example` files document every variable. Provider endpoint URLs are settings (`GROQ_API_URL`, `GEMINI_API_URL`). A build with a missing or wrong setting opens on a screen that names it (`app/src/lib/env-check.ts`), refuses plain http in an installed build, and catches a secret key put in the app by mistake. `render.yaml` lists `GROQ_BACKUP_API_KEY`.
- **`GET /coach/checks`**: 3 queries instead of up to 41.

Verified:

- Backend: 426 tests pass against real Postgres with the real `.env` present, and again with outbound HTTP blocked; ruff, ruff format and mypy clean. 22 of the tests are new (provider error classes, backup key, gateway fail-over and 10-minute bench, settings validation, JWKS outage, database outage, wrong-clock answers, query count).
- App: typecheck and lint clean; 25 tests pass (6 new: upload policy, build-settings check).
- **Live, through the real gateway with the local database:** Gemini answered 402 and was benched with one log line, Groq answered "ein Tisch -> einen Tisch (accusative)" with a valid schema, the repeat was served from the cache, and usage was recorded as 1 request, 348 + 161 tokens for Groq and nothing for Gemini.

Not verified: the Gemini request itself (no usable key). It is unchanged from before.

Decisions:

- **Groq over JSON-schema mode.** Strict schema output worked live but cost about 200 extra input tokens per call against an 8,000 tokens-a-minute limit. Plain JSON mode gave 14 of 14 valid answers, and the gateway validates every answer and now falls through on a bad one.
- **Wrong clock: accept, don't reject.** A refused answer is deleted by the app, so refusing protects nothing the learner cares about.
- **The backup key** is used as you set it up. If both keys belong to one Groq organisation they share one allowance and the backup only helps if the first key is revoked. Using a second account purely to get round rate limits may be against Groq's terms: worth a look.

### 2026-11-12: Phase 2 done (AI and OCR accuracy for German)

The work was interrupted once (a session limit, after 2.3 was saved and 2.4 was written but not yet run). It was picked up from the snapshots and this file; nothing was lost.

What changed and why:

- **Coach prompt rewritten from live answers** (`ai/prompts.py`, version 3). The model now lists its issues before it writes the explanation, and the explanation covers every error, which is what stops "No errors found." appearing above a correction. A fix must be whole words that can replace the wrong ones; for a word that has to move (verb second, separable prefix, infinitive at the end) the model gives the whole clause in the right order. The checks LanguageTool is weak at are named in the prompt, because only the AI can find those.
- **AI corrections are checked before the learner sees them.** A fix that can't be put into the sentence ("stehe ... auf", empty, bracketed) is dropped (`coach/merge.py: usable_fix`). Every AI-only correction is sent back through LanguageTool with the fix applied, in one request; if LanguageTool objects to the corrected words, the correction drops to Uncertain and stays out of the suggested text (`coach/service.py: recheck_ai_fixes`). "No errors found." is never shown while corrections are (`overall_explanation`).
- **Exercise answers are checked against the exercise** (`scanner/verify.py`, `scanner/service.py`, prompt version 2). An answer that isn't in the filled-in sentence, or a filled-in sentence that isn't the printed line with its gap filled, is Uncertain. A hint that contains the answer is replaced by one that names the grammar topic.
- **An evaluation command**, `python -m app.ai.evaluate [provider]`: 16 fixed A1 sentences (11 with one error each, 5 correct) and one 5-item exercise, sent to the real provider and scored as the learner would see them. It needs a complete `backend/.env` because settings are validated at start-up; it does not use the database.
- **Umlauts and ß in reviews** (`review/grading.py`, mirrored in `app/src/features/review/grading.ts`). "Madchen", "Maedchen", "Strasse" and the plural "Mutter" for "Mütter" are still wrong, but now get "Check ä, ö, ü and ß: they are letters of their own. Hold a, o, u or s on the keyboard to type them." Both sides are compared in one Unicode form, and new words are stored in that form (`vocabulary/schemas.py`), so a pasted "ä" made of two characters matches a typed one.
- **Text from photos is tidied before the learner sees it** (`app/src/features/scanner/text.ts: cleanReading`): a word split over two lines is joined; `heiBe`, `groB` and a Greek beta become ß; `lch`, `lst`, `ltalien` and `|ch` get their capital I back, and `SchuIe` its small l; every form of gap (`_ _ _`, `.....`, `…`, `-----`, a lone `_`) becomes `___`, which is the form the prompt and the server's checks expect. Each rule only fires on something that cannot be correct German, so right text is not touched (tested). Typed text is never "corrected": only its gaps and Unicode form are tidied when it is sent.
- **A badly read photo is called out** (`looksMisread`): when 3 or more words, and at least 15% of them, have a symbol inside, letters mixed with digits, no vowel or a capital in the middle, the review screen warns that the answers would be unreliable and says how to retake the photo. A text with no gap at all gets a quiet reminder that photos often lose them. Both notes disappear as the learner fixes the text.

Verified:

- **Live, 2026-11-12, Groq `openai/gpt-oss-120b`:** sentence coach 16 of 16, no correct sentence "corrected", no "No errors found." beside a correction; exercise 5 of 5 answers right, all fitting the printed line, no hint giving an answer away; no failed call.
- Backend: 485 tests pass against real Postgres; ruff, ruff format and mypy clean. 59 more tests than at the end of Phase 1.
- App: typecheck and lint clean; 41 tests pass (16 new: umlaut feedback with the same cases as the server, photo clean-up, misread warning).

Not verified:

- **The photo clean-up and the misread warning on real photos.** The examples are hand-written from the usual ways text recognition gets German wrong. The rules are narrow enough to be safe on correct text, but how often each misread really happens on your book, and whether 15% is the right line for the warning, can only be seen on the phone (device test steps, section 6).
- LanguageTool's re-check of AI corrections against the live public API in this session (it is tested with a stand-in; the live API was smoke-tested in the build phase).

Decisions:

- **Reading photos stays on the phone (ML Kit), not in the cloud.** The cloud option would be a vision model: Gemini's key cannot be used today (finding 2), a vision call costs far more of a free allowance than a text call, and the photo (with classmates' names on a shared worksheet) would leave the phone, which `docs/privacy.md` promises it never does. On-device reading is free, private and works without a connection; its weaker accuracy is met by the clean-up, the warning and the learner's own review of the text. Worth revisiting only if real photos turn out to be unusable.
- **Umlaut slips stay wrong.** "Mutter" and "Mütter" are different words, and the exam marks spelling. The tip tells the learner what to fix instead of loosening the check.
- **Two gaps side by side become one** in the clean-up ("__ __"): an underline read in pieces is the commoner case, and the learner sees the result before sending.
- **A doubtful AI correction is shown as Uncertain, not hidden.** The learner still sees that something may be wrong and is told to check with the teacher.

### 2026-11-12: Phase 3 done (production readiness and UX)

What changed and why:

- **Expo packages brought to the versions SDK 58 expects.** `expo-doctor` failed 1 of 20 checks: ten Expo packages were one patch release behind. `npx expo install --fix` updated them (patch versions only; `package.json` and `package-lock.json`). Now 20 of 20.
- **The keyboard no longer covers what you are typing (finding 19, which turned out to be real, not a maybe).** Expo's current guide says that Android apps now draw edge to edge, so the window does not shrink when the keyboard opens and a plain scrolling page stays underneath it. Every screen with a text input now uses one shared page (`app/src/ui/FormScroll.tsx`) that makes room for the keyboard: the twelve places are Write, Add word, the word, chapter and mistake forms, Add resource, Add a test, Add a result, Add from a message, the scanner, the review session and the Allango player. No new library: it uses React Native's own `KeyboardAvoidingView`, as the guide recommends for forms like these.
- **Long text boxes get their border back.** A field that was given its own style (the Write box, the scanner's text, chapter notes, two review cards) lost the shared border, padding and font size, because the caller's style replaced the shared one instead of adding to it. Found while working on the fields; fixed in `ui/components.tsx`.
- **Accessibility.** Each input is tied to its label, so a screen reader announces "German, edit box" and still reads back what was typed. Error messages are announced when they appear (the shared `ErrorText`, plus the failure messages on the scanner, class-task, player and add-resource screens). The progress bar reports its value. The sign-in screen now uses the shared fields, button and colours, has visible labels instead of placeholders only, and its error is announced.
- **CI builds the Android bundle** on every push (`.github/workflows/ci.yml`), so a change that type-checks but cannot be bundled for the phone is caught.
- **`scripts/snapshots-to-git.sh`** turns the snapshots into git history (section 6).
- **Docs:** README (evaluation command, scanner clean-up, release checks, the two copies of the answer check), `docs/INSTALL.md` (two new rows in the troubleshooting table), `docs/v1-trial.md` (new phone checks for the umlaut tip, the photo clean-up, the misread warning, the keyboard and the text boxes). `docs/privacy.md` needed no change: nothing new is stored or sent.

Verified:

- `expo-doctor`: 20 of 20.
- **The Android production bundle builds**: 1,424 modules compiled to Hermes bytecode (3.9 MB). Hermes compiles every regular expression when it builds the bundle, so the Unicode patterns used by the answer check and the photo clean-up are accepted by the phone's engine.
- **The Android manifest a production build generates** (read with `expo config --type introspect`, plus the permissions each library adds at build time): backup is off; the share target takes text only; microphone, shared storage and "draw over other apps" are removed; what remains is internet, vibrate, audio settings, camera, notifications and start-after-reboot (so reminders survive a restart). This matches `docs/privacy.md` and `docs/INSTALL.md`.
- Backend: 485 tests pass against real Postgres; ruff, ruff format and mypy clean (the backend did not change in this phase).
- App: typecheck and lint clean; 41 tests pass.

Not verified (all need the phone; the steps are in `docs/v1-trial.md`):

- **The keyboard fix on a real phone.** It follows Expo's documented approach and type-checks and bundles, but whether every screen leaves exactly the right space (no covered field, no empty gap, also under a tab bar and in the player) can only be seen on a device.
- The screen-reader behaviour with TalkBack.
- A real release build (EAS) and the APK's final permission list (`aapt dump permissions`).
- The new CI step on GitHub: the same command passes here, but the workflow itself has never been run.
- `scripts/snapshots-to-git.sh` beyond its dry run: commits need your approval on this machine, so it was not run.

Decisions:

- **Built-in keyboard handling, not `react-native-keyboard-controller`.** Expo's guide prefers that library for complex forms, but it needs a second native library (Reanimated) and does not run in Expo Go. These forms are simple, and one more untested native module is a real risk for a first build nobody has made yet. If the phone test shows fields still covered, that library is the next step.
- **Expo packages updated, not pinned.** The alternative was to tell `expo-doctor` to ignore the mismatch. Patch releases within one SDK are the safer side of that choice.

### 2026-11-12: Community forum (a group chat for everyone with an account) and keyboard fixes

Asked for: one text-only group chat where everyone with access can ask and answer, working for about 30 people at once without errors, and the keyboard covering or overlapping inputs fixed. Decisions and the open questions are in OPEN_QUESTIONS.md (last section).

What changed and why:

- **Backend** (`backend/app/community/`, migration `5b7e1c9a4f20`): display names, messages with replies, a WebSocket that pushes new and deleted messages, and plain requests to read, post and delete. Every write takes a transaction-level lock before it takes its number, so "everything after N" can never miss a message. A slow phone is dropped from the live list instead of slowing the others. One server process only (the list of connected phones is in memory).
- **App** (`app/src/features/community/`, `app/src/app/(app)/community/index.tsx`): `store.ts` merges messages by id and `rev` and moves its cursor only on answers from the changes request, never on a pushed message, so the timed "anything new?" request stays a real safety net; `socket.ts` is a reconnecting client (auth frame first, ping every 25 s, backoff, one immediate retry on an expired login); `useCommunity.ts` wires them and retries unsent messages with the same id; the screen is an inverted list with replies, day headings, "New messages" button, "Not sent. Tap to try again", and the name form. A card on Today opens it.
- **Keyboard:** the chat input stays above the keyboard and only adds the navigation-bar height while the keyboard is closed (`ui/useKeyboardOpen.ts`); the Words tab (a search box over a list, with no handling before) now uses `AvoidKeyboard`; `FormScroll` keeps the last button of every form screen above Android's navigation bar (outside the tab bar, and not while the keyboard is open). Every file with an input was checked for handling.
- **Docs:** README (Community forum section), `docs/privacy.md` (the chat is the one shared feature; the backup includes messages), `docs/v1-trial.md` (two-phone chat checks and the new keyboard checks), OPEN_QUESTIONS.md.

Verified:

- Backend: 527 tests pass against real Postgres (42 new), ruff, ruff format and mypy clean, `alembic check` clean. A 30-person load test against a real uvicorn server (server in its own process): each person posting about once a second, a send took 14 ms at the median and 21 ms at the 95th percentile, the message reached the other 29 phones 1 ms later, and all 9,000 deliveries arrived once each, in order. Posting as fast as possible, about 32 messages a second.
- App: typecheck and lint clean; 87 tests pass (46 new: the merge rules, the cursor rule, pending and failed sends, replies to deleted messages, the socket's auth frame, ping, silence detection, backoff, the 4401 and 4409 cases, stop, day headings). Making a pushed message move the cursor makes a test fail. `expo-doctor` 20 of 20; the Android production bundle builds.

Not verified:

- **Anything on a phone.** No emulator or `adb` exists here: the chat, the keyboard handling (including the input jumping up rather than sliding on Android) and the screen reader behaviour are untested on a device.
- **Anything on Render.** The load numbers are from a laptop with a local database; the free server has much less CPU and a network hop to the database. Whether an open chat keeps the free server awake is unknown.
- The socket client was tested with a fake WebSocket; React Native's real one has not been connected to the real server.

Decisions: voice messages not built (storage, the blocked microphone, moderation); one room, not channels; display names, never emails; Share-or-copy instead of a Copy button (no new native library); no `react-native-keyboard-controller`. Details and the rest in OPEN_QUESTIONS.md.

## 6. What is left, and what needs you

All three phases are done as far as this machine allows. Nothing below can be done from here.

### 6.1 What you have now

| | Before (2026-11-11) | Now |
|---|---|---|
| AI features | None worked: the Groq model was retired and the Gemini key has no credit | Work through Groq (`openai/gpt-oss-120b`), with the backup key as a second provider. Live test: 16 of 16 sentences, 5 of 5 exercise answers |
| Offline review answers | Deleted on any refusal, including a sign-in hiccup or a wrong phone clock | Kept until the server has them |
| German feedback | "No errors found." above a correction; broken suggested sentences; unchecked AI corrections and exercise answers | Corrections re-checked by LanguageTool; answers checked against the printed line; hints can't give the answer away |
| Umlauts and ß | "Wrong", no reason | Wrong, with a tip that says what to fix |
| Photos | Raw text | Usual misreads tidied; a bad reading gets a warning |
| Outages and setup mistakes | Generic errors, a blank screen | Say what is wrong and what to do |
| Typing | Keyboard covered the lower fields (per Expo's docs) | Page makes room for the keyboard (to confirm on the phone) |
| Tests | Backend 403 passed, 1 failed; app 19 | Backend 485; app 41; all pass |

### 6.2 Values only you can fill in

Checked on 2026-11-12 by name only (the values were not read out):

| Where | Setting | State | Where to get it |
|---|---|---|---|
| `backend/.env` | `SUPABASE_URL` | **empty** | Supabase dashboard → Project Settings → API → Project URL |
| `backend/.env` | `DATABASE_URL` | **empty** | Supabase → Connect → Session pooler; change the prefix to `postgresql+psycopg://` |
| `backend/.env` | `GROQ_API_KEY`, `GROQ_BACKUP_API_KEY` | set, working | |
| `backend/.env` | `GEMINI_API_KEY` | set, **but every call answered 402** when tested live on 2026-11-11 (prepaid billing with no credit) | Make a key in Google AI Studio under a project with no billing account (the free tier), or delete the line: the app runs on Groq alone |
| `backend/.env` | `SENTRY_DSN` | empty (optional) | sentry.io, only if you want error reports |
| `app/.env` | `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `EXPO_PUBLIC_API_URL` | **all empty** | The same Supabase page (the *publishable* key, never the secret one); the API URL is your computer's LAN address for development |
| Render dashboard | `SUPABASE_URL`, `DATABASE_URL`, `GROQ_API_KEY`, `GROQ_BACKUP_API_KEY`, optionally `GEMINI_API_KEY`, `SENTRY_DSN` | not checked from here | The same values as `backend/.env` |
| EAS (production) | the three `EXPO_PUBLIC_…` values, with the Render **https** URL | not checked from here | `docs/INSTALL.md`, step 2 |
| GitHub secret | `SUPABASE_DB_URL` | not checked from here | Turns on the nightly backup (`docs/backup-and-restore.md`) |

Until the two empty backend values are filled in, the backend refuses to start and says which one is missing. That is on purpose.

### 6.3 Put the work into git

This folder is not a git repository, and I could not make commits here. Each unit of work is a full copy of the project in `.phase-snapshots/` (git-ignored, no secrets inside). One script turns them into history: the starting point on `main`, then one commit per unit on the branch `improve/reliability-accuracy-readiness`, with a tag at the end of each phase.

```sh
sh scripts/snapshots-to-git.sh --dry-run   # lists the commits, changes nothing
sh scripts/snapshots-to-git.sh             # creates the repository and the commits
```

It never touches your working files and pushes nothing. It has only been dry-run: if a real run stops half-way, delete the `.git` folder it made and nothing else has changed. Afterwards `.phase-snapshots/` can be deleted.

### 6.4 Test on the phone

Build and install the APK (`docs/INSTALL.md`), then go through `docs/v1-trial.md`. The checks added by this work, in the order I would do them:

1. **Typing**: on every screen with a field, the field stays above the keyboard. This is the change most likely to need a second pass.
2. **Scanner on real book pages**: are gaps, ß and `Ich` right; did the clean-up change anything that was correct; does a bad photo get the warning and a good one not.
3. **Write**: "Ich habe ein Tisch gekauft." gets a correction and an explanation that agree with each other; a correct sentence gets none.
4. **Review offline**: airplane mode on, answer cards, off again; every answer arrives.
5. **Umlaut tip**: "Madchen" for "Mädchen".
6. The APK's permissions: notifications and camera, nothing else sensitive.

### 6.5 Worth a decision when you have a moment

- **The Gemini key** (above): fix it or drop it. With it fixed there is a provider that does not depend on Groq.
- **The backup Groq key.** If both keys are from one Groq organisation they share one allowance, and the backup only helps if the first key is revoked. A second account used only to get round rate limits may be against Groq's terms.
- **If the keyboard still covers fields on your phone**: the next step is `react-native-keyboard-controller` (one more native library, needs a new build).
- **If real photos read badly even when taken well**: the alternative is a cloud vision model, which costs allowance and sends the photo off the phone. Today's decision is to stay on the phone.

The earlier per-phase questions from the build are still in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).
