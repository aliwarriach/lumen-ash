# Lumen A1

A study companion for German A1: your own private study records, plus one shared chat room for the people who use the app. See the [product design](german-a1-study-companion-product-design.md) the [improvement roadmap](ROADMAP.md) and the [build history](docs/build-history.md).

| Folder | What |
|---|---|
| [backend/](backend/) | FastAPI service (Python 3.13, managed with `uv`) |
| [app/](app/) | Expo React Native app (Android) |

## One-time setup

1. **Tools:** install [uv](https://docs.astral.sh/uv/) (`brew install uv`) and Node.js 22+.
2. **Supabase:** create a free project.
   - Authentication → Sign In / Providers: leave "Allow new users to sign up" **on** and turn **on** "Confirm email" (sign-up is open; people confirm their email first).
   - Authentication → Emails → SMTP Settings: add your own sender (for example Brevo: host `smtp-relay.brevo.com`, port 587, the SMTP login and key from Brevo, a verified sender address). Supabase's built-in sender is far too limited.
   - Authentication → Emails → Templates → **Reset Password**: the email must show the code, so put `{{ .Token }}` in the body (for example "Your Lumen A1 code: {{ .Token }}"). The app's "Forgot your password?" asks for that code.
   - Authentication → URL Configuration: set **Site URL** to a page that says "email confirmed" (the confirmation link ends there; `site/confirmed.html` is one you can host anywhere) and add it to Redirect URLs.
3. **Backend config:** fill in `backend/.env` (start from `backend/.env.example`, which explains every variable). The Groq and Gemini keys go here and nowhere else. The backend refuses to start, and says why, if `SUPABASE_URL` or `DATABASE_URL` is missing or malformed.
4. **App config:** fill in `app/.env` (start from `app/.env.example`). Public values only: they end up inside the APK. If one is missing the app opens on a screen that names it.

## Load the dictionary (once, then occasionally)

Fills in articles, plurals, verb forms, English meanings, an example sentence and audio when adding words, and lets an inflected form ("gehst", "Tische") find its word. About 84,000 entries plus about 880,000 inflected forms, ~127 MB in the database (of Supabase's 500 MB), ~1 minute locally and ~4 minutes against Supabase. Example sentences come from Wiktionary and exist for about 8% of entries overall, but for about two thirds of common beginner words.

```sh
cd backend
curl -LO https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl   # 1.1 GB
uv run python -m app.dictionary.importer kaikki.org-dictionary-German.jsonl
rm kaikki.org-dictionary-German.jsonl
```

It runs in one transaction and is safe to re-run. Word data is CC BY-SA (Wiktionary); the app shows attribution.

## AI (optional)

Put `GROQ_API_KEY` (and optionally `GROQ_BACKUP_API_KEY` and `GEMINI_API_KEY`) in `backend/.env`, never in the app. With no keys, everything except AI features works. Providers are tried in order (Groq, the backup Groq key, then Gemini); one that is rate limited, down or gives an unusable answer is skipped for that request, and one with a rejected key, no credit or a retired model is left alone for ten minutes and logged. `GET /ai/quota` shows what is left today. Limits, model names and provider order are all settings; see `backend/.env.example`. Daily limits reset at midnight UTC.

Models get retired: if AI stops working, check the model names in each provider's console, change `GROQ_MODEL` or `GEMINI_MODEL`, and run `cd backend && uv run python -m app.ai.evaluate` to see how the new model does on German before relying on it. It sends 17 short requests to the real provider and prints a verdict (on 2026-11-12: 16 of 16 sentences and 5 of 5 exercise answers right). It needs `SUPABASE_URL` and `DATABASE_URL` filled in, because the settings are checked at start-up, but it never touches the database.

## Sentence coach

The **Write** tab checks German writing with [LanguageTool](https://languagetool.org)'s free public API plus our own A1 rules, then the AI explains. Text is stripped of phone numbers, emails, links and any names in `AI_REDACT_NAMES` before it leaves the backend; LanguageTool is a third-party service, so don't treat that as a privacy guarantee. For the best results load the dictionary first (above): corrections are only "Confirmed" when the dictionary backs them. Accepted corrections go into the mistake log and become retry cards.

## Today screen and reminder

The **Today** tab shows whether you're on track, a plan of up to an hour (due reviews, one weak grammar pattern, homework, writing, listening, speaking) with the reason for each item, your weak spots, and the test status. Everything is worked out from your own records when you open it. Add your tests (internal ASH tests and the Goethe A1 exam) to see a countdown, a readiness estimate with the reasons, and a revision plan. Set a daily reminder under ⋮ menu → *Account and daily reminder* (Android will ask for permission to show notifications).

## Class tasks from WhatsApp

Open **Today → ⋮ menu → Class tasks from WhatsApp → Add from a message**. Paste a message from your class chat (in WhatsApp press and hold it, tap Copy), or share it to Lumen A1 where WhatsApp offers Share. The AI proposes the tasks and dates; you check and approve them, choose a reminder, and save. Reminders are scheduled on the phone. Sharing needs the built APK: Expo Go can't receive shares, so only pasting works there. The message itself is never stored, only the tasks you approve. Screenshots aren't supported yet. Uses the "message scans" allowance (10 a day by default).

## Allango audio and video

In a chapter, add a resource with its Allango link (Add resource). Resources with a secure link show **Play**: the page opens inside the app, with the exercise's title, a done tick and an answer box underneath. Only the link is stored; the audio and video are Allango's own player. The page can move around its own site, other sites open in your browser, and **Open in browser** is always there if Allango refuses to load in the app.

## Exercise scanner

Open **Today → Scan an exercise**. Photograph one exercise from your book (you can crop to it), or choose a photo, or type it. The phone reads the text itself with Google ML Kit: the photo is never uploaded or kept. The usual misreads are tidied before you see the text (a word split over two lines, `heiBe` for `heiße`, `lch` for `Ich`, gaps in any form become `___`), and a photo that was read badly gets a warning that says to take it again. You correct the text, then the AI gives a hint for each item; the answer is shown only when you tap, with a Confirmed / Likely / Uncertain label (the AI alone never makes an answer Confirmed: our dictionary and LanguageTool must agree). You can write your own sentence and check it; accepted corrections go to the mistake log. Needs the built APK: Expo Go has no text reader (typing and pasting still work). Uses the "exercise helps" allowance (15 a day by default); nothing is stored on the server.

## Community forum

**The Community tab** (third in the bottom bar). One group chat for everyone who has an account: ask a question, answer someone, quote the message you are answering (hold a message → Reply). Text only: no pictures, video or voice (there is nowhere to store them, and the microphone is deliberately blocked).

- **Usernames.** Right after the first sign-in the app asks for a username (3 to 20 letters, numbers or underscores, unique whatever the case; names like `admin` or `teacher` are reserved) and shows nothing else until it is chosen. The same name is used in the chat. Other people see only that name, never the email. It is fixed once chosen: only a moderator (`COMMUNITY_MODERATOR_EMAILS`) can change their own.
- **Live.** New messages arrive over a WebSocket on the backend (`/community/ws`), and the app also asks "anything new?" every 25 seconds (every 4 seconds while the socket is down), so a dropped push costs seconds, never a message. A message that can't be sent stays in the list as "Not sent. Tap to try again" and is retried with the same id, so it can never post twice.
- **Deleting.** Anyone can delete their own message: the text is erased from the database and everyone sees "Message deleted". Moderators can delete anyone's: list their emails in `COMMUNITY_MODERATOR_EMAILS` (comma separated, backend settings; on Render it is in `render.yaml`). There is no editing.
- **Limits.** 2,000 characters a message and 20 messages a minute per person (`COMMUNITY_MESSAGES_PER_MINUTE`); 200 phones connected live at once (`COMMUNITY_MAX_CONNECTIONS`).
- **One server process only.** The list of connected phones is in memory (`backend/Dockerfile` starts one process; Render's free plan runs one). Do not scale it out without moving that list somewhere shared.
- **Ask the Community.** A link under a word, a practice exercise (grammar practice and sentence lessons), a scanned exercise item, a chapter, a grammar rule and the resource player (a speech-bubble icon in its bottom bar) opens a sheet: the item as a small card, quick prompts ("I don't understand this." …) and the question. It posts to the chat like any message, with the card above it (`attachment` on the message: a kind, a title and up to 6 lines, plain text only, never a link; erased with the message). The sheet stays on the screen, so a practice round or a scanned exercise is not lost; "Open the chat" goes there after sending. Cards are built by plain rules in `app/src/features/community/ask.ts` (tested).
- **Everything else stays private.** This is the only shared feature: every other table is still readable by its owner alone.
- **Accounts.** Anyone can create an account in the app (email and password, then the confirmation link in the email). "Forgot your password?" emails a code to type into the app. There is no Google sign-in yet: it needs a published Google consent screen, which needs a domain you own.

Code: `backend/app/community/` (read the docstring in `service.py` before touching the write lock) and `app/src/features/community/` (`store.ts` holds the merge rules, `socket.ts` the reconnecting client; both have tests). The backend's 30-person load test is `backend/tests/test_community_load.py`.

## Run locally

```sh
# Backend: http://localhost:8000/docs
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0

# App (other terminal): scan the QR code with Expo Go on the Android phone
# (sharing from other apps needs the built APK, see "Class tasks from WhatsApp")
cd app
npm install
npm start
```

On the phone, `EXPO_PUBLIC_API_URL` must be your computer's LAN IP, not `localhost`.

## Checks

```sh
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests && uv run pytest
cd app && npm run typecheck && npm run lint && npm test
```

Database tests need an empty throwaway Postgres (they wipe every table). Point `TEST_DATABASE_URL` at it, e.g. `TEST_DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/lumen_test uv run pytest`. Without it, those tests are skipped.

Before a release build, also check the app's packages and that the Android bundle builds:

```sh
cd app && npx expo-doctor && npx expo export --platform android --output-dir /tmp/lumen-export
```

`expo-doctor` complains when Expo publishes new patch versions of its packages; `npx expo install --fix` brings them in line.

After changing backend endpoints, regenerate the app's typed client: `cd app && npm run gen:api`.

The answer check for reviews exists twice, on the server (`backend/app/review/grading.py`) and in the app for instant offline feedback (`app/src/features/review/grading.ts`). Change both together: their tests use the same cases.

Every new table's migration must `ENABLE ROW LEVEL SECURITY` (a test checks this). It keeps Supabase's public Data API from reaching learner data.

## Deploy and release

- **Backend:** in Render, create a Blueprint from this repo ([render.yaml](render.yaml)), then set the environment variables in the dashboard.
- **App:** build a signed APK and install it: [docs/INSTALL.md](docs/INSTALL.md).
- **Backups:** add the `SUPABASE_DB_URL` repository secret on GitHub to turn on the nightly backup. The repository must be private. Each night's dump is restored into a throwaway database and verified; how to restore for real is in [docs/backup-and-restore.md](docs/backup-and-restore.md).
- **Privacy:** what is stored, who receives what, and the limits: [docs/privacy.md](docs/privacy.md).
- **Before calling it v1:** the phone checklist and two-week trial in [docs/v1-trial.md](docs/v1-trial.md).

Word data from Wiktionary will be used under CC BY-SA; attribution appears in the app.
