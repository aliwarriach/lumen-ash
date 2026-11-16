# Build history: German A1 Study Companion

This is the original build roadmap, kept as a record of what each feature is and how it was built. The current improvement roadmap is [ROADMAP.md](../ROADMAP.md).

It turned [the product design](../german-a1-study-companion-product-design.md) into phases we could build. Each phase leaves the app working and usable, and each one builds on the one before it.

## Constraints

- **$0 to run.** Only free tiers and open-source tools.
- **Android only.** We build an APK and install it directly; no Play Store.
- **One backend service, no dedicated workers.** No Celery, no Redis, no queue.
- **AI is optional.** Every core feature (reviews, vocabulary, mistake log, course map) works with no AI at all. When the AI quota runs out, AI features show a clear message instead of breaking.
- **Accuracy over cleverness.** Dictionary data and rule-based checks come first. AI explains; it doesn't decide.

## Stack

| Area | Choice |
|---|---|
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, `uv`, Ruff, pytest |
| Database, login, files | Supabase free plan (Postgres, Auth, Storage, `pg_cron`) |
| App | React Native + Expo (Expo Router, TanStack Query, Zustand), Android APK |
| API contract | TypeScript client generated from FastAPI's OpenAPI schema |
| Hosting | Render free plan (Cloud Run as fallback) |
| Review scheduling | FSRS |
| Grammar checks | LanguageTool free public API |
| AI | Gemini (primary) and Groq (secondary) through one internal adapter |
| Word data and audio | Wiktionary / kaikki.org import, then `expo-speech` as a fallback voice |
| Reminders | Notifications scheduled on the phone |
| Errors | Sentry free plan |

### Repository layout

```
lumen-ash/
  backend/          FastAPI service (modular monolith)
    app/
      core/         config, auth, database, rate limiting
      ai/           provider adapter, quotas, cache
      course/       chapters, topics, Allango links
      vocabulary/   words, dictionary lookup, audio
      review/       FSRS cards and daily queue
      grammar/      grammar patterns and accuracy
      mistakes/     mistake log and patterns
      coach/        sentence feedback
      exams/        test dates, results, readiness
      capture/      WhatsApp capture and tasks
    migrations/
  app/              Expo React Native app
  docs/
```

---

## AI usage and limits (applies to every phase)

The free quotas are shared, so no single user may be able to use them up. This is built in Phase 5, before any feature that calls AI.

### Model choice

- **Default to the lightest model each provider offers** (for example, Gemini's Flash-Lite tier). Lighter models have the highest free limits.
- We confirm the exact model names when we set it up, since providers rename and retire models often. Model names live in config, never in code.
- **Fallback order:** Gemini → Groq → "AI unavailable, try later". We only switch providers when one returns a rate-limit or quota error.

### Using as few tokens as possible

How we write the requests matters more than which model we pick:

1. **Ask AI only when needed.** Dictionary data fills in articles and plurals, and LanguageTool finds the errors. AI only explains and generates practice.
2. **Short, fixed prompts.** We send just the sentence, the LanguageTool findings and a short list of candidate grammar-pattern IDs. We never send the learner's history.
3. **Structured output with a hard cap.** Responses come back as JSON with a strict `max_output_tokens`.
4. **No conversation memory.** Every call stands alone.
5. **Cache answers.** Identical inputs (after normalising the text) return the stored answer, so the same sentence is never paid for twice.

### Rate limiting (stored in Postgres, no Redis)

| Layer | Purpose | How |
|---|---|---|
| **Per-user daily budget** | One user can't drain the shared quota | `ai_usage` table: requests and tokens per user per day, checked before every call and updated in the same database transaction |
| **Per-feature caps** | Spread each user's budget across features | e.g. sentence checks per day, screenshot extractions per day (values set in config) |
| **Global daily ceiling** | Stay safely under each provider's free limit | Total usage per provider per day, stopping at about 80% of the published free limit |
| **Short-burst throttle** | Stop spam taps and loops | Per-user requests per minute on AI endpoints |

- Token counts come from each provider's own usage report in the response, not from our estimates.
- The app shows the learner what's left: *"8 sentence checks left today."*
- Daily counters reset by date, so nothing scheduled is needed.

### Key safety

- API keys live **only on the backend**: in a local `.env` (git-ignored) and in Render's environment variables.
- Keys never go into the mobile app, because an APK can be unpacked.
- Keys shouldn't be pasted into chat. Put them straight into `.env`.

---

## Phases

### Phase 0: Foundations

**Status:** code done. Waiting on the Supabase project, Render deploy and a test on the phone.

**Goal:** an empty app that can log in, call the backend and be deployed.

- Set up the repository, `backend/` and `app/`, linting, formatting and pytest.
- Create the Supabase project. Turn off open sign-ups (invite or allowlist only) so strangers can't use up the AI quota.
- In FastAPI: settings, database connection, Alembic, Supabase login-token check, and a health endpoint.
- In the Expo app: login screen, Supabase auth, generated API client, basic navigation.
- Deploy to Render, add Sentry to both sides, and run tests and lint in GitHub Actions.
- Add a nightly `pg_dump` backup through a scheduled GitHub Action, because the free Supabase plan has no backups.

**Done when:** the APK installs on the phone, the learner logs in, and the app shows data from the deployed backend.

### Phase 1: Course map

**Status:** code done (backend tested; app screens not yet run on a phone).

**Goal:** the A1 course appears as chapters with progress.

- Chapters, topics, book pages, and links to Allango audio, video and exercises. Links and references only; no copyrighted files are stored.
- Workbook exercise checklist per chapter.
- Course map screen: completed, pending and needs-revision for each chapter.

**Done when:** the learner can open a chapter and see what's done and what's pending.

### Phase 2: Vocabulary with real dictionary data

**Status:** code done (backend tested, dictionary import tested on the full dump; app screens not yet run on a phone).

**Goal:** complete word records that fill themselves in.

- Import German Wiktionary data (articles, plurals, verb conjugations, audio links) into Postgres. This is a one-time script, re-run occasionally.
- Word capture: type "Tisch" and get *der Tisch, die Tische*, with audio.
- Noun and verb fields as described in the design doc, including the learner's own sentence, chapter and source.
- Audio: a Wiktionary native-speaker recording if one exists, otherwise `expo-speech`.
- Word stages: New → Learning → Familiar → Usable → Mastered.
- Show Wiktionary attribution (CC BY-SA) in the app.

**Done when:** adding a noun or verb takes seconds and the details are correct without any AI.

### Phase 3: Review engine

**Status:** code done (backend tested, including a full New → Mastered walk-through; app screens not yet run on a phone). Sentence cards are still self-rated; the Phase 6 coach does not check them yet.

**Goal:** the daily review queue.

- FSRS scheduling for each card, with due cards worked out when requested.
- Card types: word recall, article and plural, and sentence production. Listening and error-retry cards come in later phases.
- A failed or low-confidence answer brings the card back right away.
- Promote a word to "Mastered" only after it is used correctly in a fresh sentence across several sessions.
- Cache the queue on the phone so reviews still work while Render is waking up or there is no signal.

**Done when:** the learner opens the app and reviews exactly what's due.

### Phase 4: Mistake log and grammar tracker

**Status:** code done (backend tested; app screens bundle but have not been run on a phone yet). 17 A1 patterns are written in `backend/app/grammar/catalog.py` and a teacher should check them. Accuracy comes from logged mistakes, article and plural answers, the article in typed nouns, and mistake retries. Sentence cards add no grammar evidence until they are checked automatically; accepting a coach correction does add evidence.

**Goal:** mistakes become the curriculum.

- A grammar-pattern list (verb in second position, accusative, separable verbs, modal verbs, and so on), each with an explanation, examples, common mistakes and chapter links.
- Mistake log entries: wrong version, corrected version, category, grammar rule, related words, chapter, and whether it's a repeat.
- Group mistakes into patterns and track accuracy for each grammar rule.
- Turn each mistake into an error-retry review card.

**Done when:** the learner can see their top weak patterns, with evidence.

### Phase 5: AI layer, quotas and rate limiting

**Status:** code done (backend tested against real Postgres with fake providers; the real Gemini and Groq calls have not been run because no keys are set yet). Before relying on it: put the keys in `backend/.env`, check the model names and free limits in each provider's console, and set the `*_CEILING` values to about 80% of what you see. Fallback also happens on outages and timeouts, not only rate limits. The prompt templates in `backend/app/ai/prompts.py` are first drafts that Phases 6 and 9 will refine.

**Goal:** safe, cheap, swappable AI access. Nothing user-facing yet.

- Provider adapter with Gemini and Groq behind one interface.
- `ai_usage` and `ai_cache` tables, per-user and global budgets, burst throttle, and provider fallback.
- Prompt templates with structured-output schemas and token caps.
- Strip names and phone numbers from text before it is sent to a provider.
- Quota endpoint plus a "remaining today" display in the app.
- Tests: budget enforcement, fallback when a provider returns a rate-limit error, cache hits, and behaviour when both providers are unavailable.

**Done when:** a test user who hits their limit is blocked cleanly, other users are unaffected, and switching providers is a config change.

### Phase 6: Sentence coach

**Status:** code done (backend tested against real Postgres with fake AI providers, and the LanguageTool client smoke-tested against the live public API; app screen type-checks, lints and bundles for Android but has not been run on a phone; real Gemini/Groq calls still untested). It lives in a new **Write** tab. What is and isn't covered:

- **Confirmed** needs the dictionary import (Phase 2): our rules check LanguageTool's fix against gender, plural and verb-form data, for five patterns (accusative, noun gender, capitals, plural forms, present endings). Without the dictionary nothing is Confirmed.
- **Likely** also covers LanguageTool alone when it is reasonably sure; **Uncertain** is where LanguageTool and the AI disagree or LanguageTool is unsure of itself.
- LanguageTool misses many A1 mistakes (verb position, `kein`/`nicht`, modal verbs, dative after `mit`, W-questions). Those only appear if the AI notices them, as "Likely".
- If one checker is down the other still works; if both are down nothing is saved and the learner is told, never "no mistakes found".
- **Not done:** checking the learner's sentence-card answers in Review automatically (see Phase 3). It changes how words reach "Mastered", so it needs a decision first.

**Goal:** trustworthy feedback on what the learner writes.

- LanguageTool check → map to our grammar patterns → AI explanation at A1 level, plus 2–3 practice sentences.
- **Confidence labels:**
  - **Confirmed:** LanguageTool and our pattern rules agree.
  - **Likely:** only the AI flagged it.
  - **Uncertain:** shown with the warning "verify with your teacher".
- The learner can accept, reject or flag each correction. Accepted corrections go into the mistake log automatically.
- Writing tasks such as "5 sentences about your day" are built on the same flow.

**Done when:** the design doc's "Ich habe ein Tisch gekauft" example produces a confirmed accusative-case correction with an explanation.

### Phase 7: Daily plan and dashboard

**Status:** code done (backend tested against real Postgres; app screens type-check, lint and bundle for Android but have not been run on a phone; the daily reminder has not been tried on a real device). The new **Today** tab is the home screen and answers the four questions in order. What isn't there yet:

- **"Am I ready for the next test?"** shows a plain "not set up yet" message. Test dates and readiness are Phase 8; nothing is guessed.
- **Listening and speaking aren't tracked** (that is "after v1"). A listening item is a chapter audio you can mark done; speaking is a list of words you tick off yourself on the phone.
- **The reminder is the same text every day** at a fixed time. Nothing can run in the background to check whether you've already studied, so a reminder may arrive after you have. Android may also deliver it a few minutes late.
- "On track" has no test date to measure against, so it means "studying regularly and not letting reviews pile up".

**Goal:** the app answers "What should I do today?"

- A daily plan built from data: due reviews, one weak grammar pattern, a listening item, speaking, writing and pending homework. It fits 30–60 minutes.
- Every item says why it's there: *"Article accuracy is 61%."*
- Dashboard: streak, cards due, vocabulary mastered, chapter completion, grammar accuracy, priority weak areas.
- Daily reminder notifications scheduled on the phone.

**Done when:** the four dashboard questions from the design doc are answered on one screen.

### Phase 8: Test preparation

**Status:** code done (backend tested against real Postgres; app screens type-check, lint and bundle for Android but have not been run on a phone). Add tests under **Today → Am I ready for the next test?** How the estimate works, so you can judge it:

- **Per chapter:** 40% vocabulary (share of its words that are Usable or Mastered), 40% grammar (accuracy on the patterns you linked to the chapter, last 30 days, needs 3 checked answers), 20% workbook exercises marked done. Parts with no evidence are left out, not counted as zero.
- **Overall:** the mean of the chapter scores (a chapter with no evidence counts as 0 and is listed as a gap), blended 50/50 with your last three practice tests when you have entered some. It is compared with your own goal (default 85%): at or above is "ready", within 10 points "almost", otherwise "not ready yet: focus on Chapters 4–6".
- It is a rough estimate, not a prediction of your mark. Reading, listening, writing and speaking aren't tracked by the app, so they only appear from section scores you enter with a practice result.
- **Revision plan:** nothing changes until 14 days before; then each day gets one weak chapter (rotating through them, 10 to 20 minutes, more as the test nears) and it joins the Today plan, ahead of grammar in the last 3 days. It is ticked once you review 5 cards from that chapter.
- Not done: editing a test or a result after saving (delete and re-add).

**Goal:** know your readiness before each test.

- Test dates with countdown, for internal ASH tests and the Goethe A1 exam.
- Entry of practice and internal test results.
- Readiness by chapter and by skill (vocabulary, grammar), with the gaps listed.
- A focused revision plan as the test gets close. It feeds into the daily plan.

**Done when:** the app can say *"Not ready yet: focus on Chapters 4–6"* and explain why.

### Phase 9: WhatsApp capture and reminders

**Status:** code done for **text** (backend tested against real Postgres with fake AI providers; app screens type-check, lint and bundle for Android, and the build config adds the Android share target, but none of it has been run on a phone, and the real Gemini/Groq calls are still untested). **Screenshots are not built**: see below. How it works:

- **Getting a message in:** paste it (press and hold the message in WhatsApp → Copy), or share it to Lumen A1 where WhatsApp offers Share. Sharing needs the built APK; Expo Go can't receive shares. The shared text is put in a box first so you can see, and trim, exactly what is sent.
- **Finding the tasks:** the AI lists tasks (homework, deadline, test, event, other) and copies the date words exactly. **We work out the real date ourselves** (German and English: *Freitag*, *morgen*, *15.12.*, *in 3 Tagen*, *nächste Woche Montag* …) relative to your own today. If the AI gives date words that aren't in the message, the date is dropped and you choose it. Links are found without AI and never sent to it.
- **You approve everything:** each proposed task can be edited, unticked, given a date and a reminder before anything is saved. A task you already have is left unticked. If the AI is down or out of allowance you are told, and you can add tasks by hand.
- **Only approved tasks are stored.** The message itself is never saved, so other people's names and numbers in it aren't kept.
- **Reminders:** one per task, scheduled on the phone: the evening before at 18:00, or the morning of at 08:00 if that has passed (you can pick or turn it off). The server keeps each reminder time and the phone re-creates its schedule whenever it loads the tasks, so reminders return after a reinstall. Ticking a task off or deleting it cancels its reminder. Android may deliver a reminder a few minutes late.
- **Today plan:** open tasks due within 2 days (or overdue) come right after reviews; those due within a week come after workbook homework; the plan names why ("From your class chat: due tomorrow."). Tasks with no date, or more than a week away, stay in **Today → Class tasks** only.
- **Not done:** screenshots. Reading them needs either on-device text recognition (a native library I couldn't test against this React Native version, before any build has been tried on the phone) or sending the image to Google's AI, which would also send classmates' names and numbers. Until you decide, the app only offers itself as a share target for text, and an image shared by other means gets a message saying to copy the text instead.

**Done when:** a homework message shared from WhatsApp becomes a reminder in under a minute.

### Phase 10: Hardening and v1 release

**Status:** code and documents done; the release itself needs you. Backend: all tests pass against real Postgres. App: type-checks, lints, bundles for Android and has its first unit tests (`npm test`). Nothing has been built as a release APK or run on a phone, and the new nightly-backup workflow has not been run on GitHub. What was done:

- **Offline, retries, errors:** every request now has a one-minute limit (the free server takes up to a minute to wake) instead of hanging; no connection or a slow server give plain messages saying what to do; failed reads are retried only when retrying can help (no connection, slow, server error), not for "not found" or "invalid". The app pings the server on opening and when it returns to the foreground so the wake-up happens early, and loading screens say why they are slow after 8 seconds. The review session no longer spins for ever when the queue can't load. A crashing screen shows "Something went wrong, try again" instead of a blank page. Sign-in survives a lost connection. Answers made offline still wait on the phone and upload later (Phase 3).
- **Backups you can trust:** the nightly backup is now restored into a throwaway database and checked every night (right migration version, every table and column, row-level security, no table smaller than the live one); a failure turns the job red. Run for real on a local copy with data made through the API: dump, restore, verify, and the API served it. Found and fixed a recovery gap: the dump holds no Supabase accounts, so a new project's login would own nothing; `python -m app.remap_user` re-links the data and is tested. Procedure in [docs/backup-and-restore.md](backup-and-restore.md).
- **Privacy review** ([docs/privacy.md](privacy.md)), with fixes: Sentry would have attached request bodies and local variables (your sentences and pasted class messages) to every error report; switched off and tested (the old settings were shown to leak). The AI answer cache kept answers for ever; now deleted after 30 days unused. Android's cloud backup of the app's data (including the saved sign-in) is off. The release build drops three permissions the app never uses. A test searches every text column of the database after a scan and a writing check and finds no name, phone number or email. Confirmed: no microphone, location, contacts or camera permission, so recordings can't exist.
- **Release build and install guide:** a `production` build profile, and [docs/INSTALL.md](INSTALL.md) covering building, backing up the signing key, installing, updating and what each error means.
- **The trial:** [docs/v1-trial.md](v1-trial.md) has a first-day checklist for the phone and a proposed definition of a blocking issue with a daily log.

**Done when:** the learner uses it daily for two weeks with no blocking issues.

### Phase 11: Exercise scanner

**Status:** code done; nothing has run on a phone, so reading real book pages is untested, and the real Gemini/Groq calls are untested too. The backend is tested against real Postgres with fake AI and LanguageTool (`backend/app/scanner`, `POST /scanner/help`); the app type-checks, lints, bundles for Android and has unit tests for the text helpers. What was built, and where it differs from the plan below:

- **Reading:** `expo-text-extractor` 2.0.0 (a 40-line Expo module around ML Kit's Latin text recogniser, MIT, one maintainer, last release February 2026) with `expo-image-picker` for the camera, gallery and crop. I read its source before choosing it. The recogniser is the Play-services kind, so the APK stays small but the phone needs Google Play services, and its model may download the first time. Returns blocks of text, no positions, so layout (tables, columns) is lost. It is loaded on first use, so Expo Go shows a message instead of crashing and typing still works.
- **Photo:** cropped by the learner to one exercise, read, and the cache copy deleted straight away. Never uploaded. The release build now has the **camera permission** (the image picker declares it); its microphone permission is blocked.
- **Screen:** Today → Scan an exercise: take, choose or type → edit the text → hints and answers. Hint on tap, answer on tap, and a box to write your own sentence, which goes through the Phase 6 coach so corrections can be accepted into the mistake log.
- **Answers and labels:** one AI call per exercise (`exercise_help`, 15 a day, same cache and Gemini → Groq fallback). Each answer's filled-in sentence is checked by LanguageTool in one request. **Confirmed** = our dictionary proves the verb ending (e.g. *ich gehe*) and LanguageTool found nothing wrong; **Likely** = the AI's answer with nothing against it (or LanguageTool unavailable); **Uncertain** = LanguageTool objects or the AI says it is unsure. The AI alone never makes an answer Confirmed. Only verb endings can be confirmed so far: articles, cases and word order stay Likely. (A first version confirmed "kauft einen" because *kauft* checked out; a test caught it, and an answer with anything the dictionary can't prove is now never confirmed.)
- **Limits:** the AI is told to skip items that need a picture, audio, a table or text that isn't shown, and to say what it left out; the app shows that sentence. At most 8 items and about 2,400 characters per exercise. Nothing is stored on the server.

**Goal:** photograph an exercise from the book or a worksheet and get help with it, without spending AI quota on reading the photo.

- **Reading the photo happens on the phone**, with Google ML Kit text recognition (free, offline, no server, no quota). It reads clean printed Latin text, umlauts and ß included. It is a native module, so it needs the development build or APK, not Expo Go.
- **You see the recognised text first** and can correct it and delete names before anything is sent. From then on it is ordinary text, so the existing redaction, cache and Gemini → Groq fallback all apply.
- **The AI answers as text** through the Phase 5 layer, with its own daily cap. Answers in German go through the Phase 6 checks (LanguageTool and our dictionary rules), so each one gets a Confirmed, Likely or Uncertain label.
- **Hint first, answer on tap**, then you can try it yourself and accept the corrections into the mistake log.
- **The photo is never stored.**
- **Limits:** exercises that depend on pictures, audio (listening tasks) or the page layout (matching columns, gaps in a table) only partly survive as text. The scanner says so instead of guessing.
- Pick and vet the ML Kit wrapper when we build it: the Expo ones are small community packages, so check maintenance first or write a thin module of our own.

**Done when:** a photo of a Netzwerk neu grammar exercise gives the correct text to review, and hints and checked answers for each item.

### Phase 12: Allango audio and video inside the app

**Status:** code done; never run on a phone, so the key question (does Allango's player work inside the app?) is still unanswered. App type-checks, lints and bundles for Android; the navigation rules have unit tests. No backend change: resources already store a link. What was built:

- **Player screen** (`app/src/app/(app)/player/[id].tsx`): a chapter resource with a secure (https) link now shows **Play** instead of Open and opens in an in-app web view (`react-native-webview` 14.0.1, the Expo-bundled version, no extra permissions). Under the page: the title and book reference, a **done** tick for the resource, an answer box checked by the sentence coach (corrections can go to the mistake log), and a link to the Phase 11 scanner for hints. Back-in-page, Reload and **Open in browser** sit above them.
- **The page can't turn the app into a browser** (`features/player/policy.ts`, tested): it may move around its own site (the saved link's main domain and sub-domains) over https. Another site or an http page opens in the phone's browser. Anything that isn't a web link (intent:, file:, javascript:, data:, or a link with `user@` in it) is refused. No pop-up windows, no access to the phone's files.
- **If it refuses** (the earlier automated request got a 403): the player shows what happened and what to do, and Open in browser is always one tap away. An http link goes straight to the browser.
- **Links only.** Nothing from Allango is copied or stored. The view keeps Allango's own cookies (so a sign-in is remembered) in the app's private web storage.
- **Not done:** scanning the media code printed in the book to jump to the right audio (depends on how Netzwerk neu prints its codes: see OPEN_QUESTIONS.md), and any proof that audio keeps playing with the screen off.

**Goal:** play the Allango media for an exercise without leaving the app.

- allango is Klett's browser app (a web app, Chrome 79 or newer). According to Klett, playing media is free; an account is only needed to bookmark, keep lists or save offline.
- **Show the allango page inside the app** in an in-app browser view, so its own player is used, your login (if any) is remembered, and you never leave the app. Below or beside it: the exercise, your answer box, and a "done" tick for the chapter resource.
- **We store links, never Allango's files.** Pulling their audio and video files into our own player would mean copying copyrighted material and probably breaking their terms, so the plan is to use their player inside our app.
- **What we know (checked 2026-11-11 on a real link):** allango links can point straight at one audio on one book page (`...?page=8&id=...&type=audio`), so each exercise resource can store its own link. The page is a JavaScript app (an empty shell until its script runs), so it needs a real browser engine, which an in-app view has. It forbids being embedded in other *websites* (`frame-ancestors 'none'`, `X-Frame-Options: SAMEORIGIN`), but an in-app view loads it as the main page, so those rules don't apply. Its media comes from Amazon's CDN. An automated request got `403`, probably bot protection; a real phone browser should not.
- **Test first:** whether allango works inside the in-app browser (the 403, login, playback, audio continuing with the screen off). If it refuses, fall back to opening it in the phone's browser.
- **Maybe:** scan the media code printed in the book to jump straight to the right audio. This depends on how Netzwerk neu prints its allango links, to be checked.

**Done when:** tapping an exercise's audio in a chapter plays it inside the app, and you can answer and tick it done on the same screen.

---

## After v1

- Listening sessions: listen, read along, shadow, comprehension questions, listening cards.
- Speaking practice: recordings, self-rating, hesitation tracking. Speech analysis only if a free option is good enough.
- Deeper writing feedback and progress over time.
- A2 and B1 content and levels.

## Decisions

1. **Secondary AI provider: Groq** (free tier, open models). Gemini stays primary.
2. **Users:** one learner at launch, built for several. Every record belongs to a user, and quotas are per user. Sign-up stays invite-only until we choose to open it.
3. **Urdu:** English is the main language of meaning. Urdu is an optional field the learner fills in for a few words.
