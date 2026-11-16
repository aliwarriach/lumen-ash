# Open questions

Things that need a decision, a check, or a real-world test, collected per phase so we can go through them together at the end. Each phase adds its own section when it is built.

Legend: **Decide** = needs your choice. **Check** = needs someone to verify it. **Do** = a setup or test step that only you can do.

**Status (2026-11-11):** you chose to go with my recommendation for every **Decide** item: the defaults as built stand until you ask for a change. The **Check** and **Do** items are still open; they need the phone and your accounts.

## At a glance

| Phase | Status | Decide | Check | Do | What kind of questions |
|---|---|---|---|---|---|
| Whole project | n/a | 0 | 0 | 2 | No git repository; nothing run on the phone yet |
| 0 Foundations | built | 0 | 0 | 2 | Setup only: Supabase, Render, APK, backups |
| 1 Course map | built | 0 | 0 | 1 | Phone test only |
| 2 Vocabulary | built | 0 | 0 | 2 | Load the dictionary, phone test |
| 3 Review engine | built | 2 | 0 | 1 | Auto-checking sentence cards, new-card limit |
| 4 Mistake log, grammar | built | 0 | 1 | 1 | A teacher must check the 17 patterns |
| 5 AI layer | built | 2 | 1 | 1 | Keys, model names, free limits, reset time |
| 6 Sentence coach | built | 4 | 1 | 1 | Labels, missing A1 checks, privacy, teacher check |
| 7 Daily plan, dashboard | built | 4 | 0 | 1 | Plan length and order, tracking, reminder |
| 8 Test preparation | built | 7 | 1 | 2 | Readiness formula, goals, what counts as evidence |
| 9 WhatsApp capture | built (text only) | 8 | 4 | 3 | Screenshots, reminder times, how dates are read, privacy, real messages |
| 10 Hardening, release | built (release needs you) | 6 | 4 | 3 | Build method, what blocking means, privacy limits, first build, trial restore |
| 11 Exercise scanner | built (untested on a phone) | 8 | 5 | 2 | Text reader choice, camera permission, caps, what can be Confirmed, real book pages |
| 12 Allango in the app | built (untested on a phone) | 4 | 4 | 1 | Does Allango play inside the app, sign-in, audio with the screen off |
| Improvement work (2026-11-11 to 12) | done (untested on a phone) | 4 | 5 | 4 | Settings to fill in, git history, keyboard and photo clean-up on the phone, Gemini and backup keys |
| Community forum (2026-11-12) | built (untested on a phone) | 9 | 5 | 4 | Accounts for 30 people, voice, moderators, limits, retention, is the server fast enough |

Every built phase has at least one open item, but the early ones (0 to 2) are only setup and phone testing: they raise no design decisions. The real decisions pile up from Phase 3 onwards, where the app starts judging your work.

## Across the whole project

- **Do:** the project folder is not a git repository, so there is no history and no way to commit or open a PR. Should we `git init` and set up a remote? (The GitHub Actions in `.github/` only run once it is on GitHub.) *Update 2026-11-12: `sh scripts/snapshots-to-git.sh` now creates the repository with the improvement work as history (see the last section). The remote is still yours to set up.*
- **Do:** none of the app screens from Phases 1–9 have been run on the phone. They type-check, lint and bundle for Android, nothing more.

## Phase 0: Foundations

- **Do:** create the Supabase project (invite-only sign-up), deploy to Render, set the environment variables, and install the APK on the phone.
- **Do:** confirm the nightly backup action works, and later test restoring from it (Phase 10).

## Phase 1: Course map

- **Do:** run the course screens on the phone.

## Phase 2: Vocabulary

- **Do:** load the Wiktionary dictionary (about 1.1 GB download, steps in the README). Later phases lean on it: without it nothing in the sentence coach is "Confirmed".
- **Do:** run the word screens on the phone.

## Phase 3: Review engine

- **Decide:** sentence cards are still self-rated. Should they be checked automatically by the sentence coach? That changes how words reach "Mastered". If yes, should only Confirmed corrections count as wrong, so an Uncertain one never counts against a word?
- **Decide:** the daily limit of 15 new cards. Right for you?
- **Do:** run reviews on the phone, including offline.

## Phase 4: Mistake log and grammar tracker

- **Check:** a teacher should read the 17 patterns in `backend/app/grammar/catalog.py` (explanations, examples, common mistakes). The app's corrections are only as good as this list.
- **Do:** run the mistake and grammar screens on the phone.

## Phase 5: AI layer

- **Do:** add `GEMINI_API_KEY` and `GROQ_API_KEY` to `backend/.env` and Render, then send one real request through each. Real provider calls have never been made.
- **Check:** the model names (`gemini-2.5-flash-lite`, `llama-3.1-8b-instant`) and the free limits behind the `*_CEILING` settings. Google no longer publishes per-model free limits and one source says Groq's free Llama 3.1 8B is now "contact sales".
- **Decide:** fallback also happens on outages and timeouts, not only rate limits as the roadmap says. Keep that?
- **Decide:** daily limits reset at midnight UTC (05:00 in Pakistan). Fine, or should the reset time suit your day?

## Phase 6: Sentence coach

- **Decide:** the labels. You defined Likely as "only the AI flagged it". I also made it cover LanguageTool alone when it is reasonably sure, and LanguageTool plus the AI agreeing. Otherwise every ordinary spelling fix says "verify with your teacher". OK?
- **Decide:** LanguageTool misses many A1 mistakes (verb position, `kein`/`nicht`, modal verbs, dative after `mit`, W-questions). Only the AI catches those, as Likely. Should we write our own rule checks for the most common ones?
- **Decide:** the free public LanguageTool API is a third-party service. Text is stripped of phone numbers, emails, links and listed names first, but arbitrary names can't be detected. Acceptable, or self-host / switch it off?
- **Decide:** only five patterns can be Confirmed (accusative, noun gender, capitals, plural, present endings). Extend the list?
- **Check:** the A1 explanations the rules write (for example the accusative one) should be read by a teacher along with the catalog.
- **Do:** try the Write tab on the phone with real sentences.

## Phase 7: Daily plan and dashboard

- **Decide:** "on track" is still judged without the test date (Phase 8 added tests but did not change this). It means "studying on most days and reviews not piling up" (at least 60% of days, under 40 cards waiting). Right thresholds?
- **Decide:** the plan caps at 60 minutes and drops lower-priority items when over. Is 30–60 minutes right for you, and is the priority order (review, grammar, homework, writing, listening, speaking) right?
- **Decide:** listening and speaking aren't tracked (the roadmap puts them after v1). Should a simple tracker come sooner, for example a self-rated 5-minute speaking log?
- **Decide:** the reminder says the same thing every day at a fixed time, because nothing can run in the background to see whether you already studied. Fine, or should it be smarter (needs a worker, which the stack rules out)?
- **Do:** try the Today screen and the reminder on a real phone (permission prompt, time of delivery).

## Phase 8: Test preparation

- **Decide:** the readiness formula. A chapter is 40% vocabulary (words Usable or Mastered), 40% grammar accuracy, 20% workbook; the overall figure is blended 50/50 with your last three practice tests; "almost" is within 10 points of your goal. Do these weights and thresholds feel right once you see real numbers?
- **Decide:** a chapter with no evidence at all counts as 0, so a chapter you simply haven't entered words for pulls you down and shows as a gap. Right, or should unstarted chapters be left out until you begin them?
- **Decide:** "secure" means a word is Usable (reliably produced over at least a week) or Mastered. Mastered is stricter (own sentences on 2 different days). Is Usable the right bar for a test?
- **Decide:** the default goal is 85% for both test kinds (your internal-result goal from the design). Set the Goethe A1 goal yourself; the app deliberately doesn't state official pass marks.
- **Decide:** revision starts 14 days out, one chapter a day, 10 / 15 / 20 minutes as the test nears. Too early or too little?
- **Decide:** reading, listening, writing and speaking are only known from section scores you type in with a practice result. Worth building real practice for them (listening and speaking are "after v1")?
- **Decide:** only practice results count towards readiness; the real result is stored but is not used for other tests. Should a real internal result (say Test 1) feed the Goethe estimate?
- **Check:** whether chapter numbers in your course match how you will group tests (for example "Chapters 1–6"). Chapters and grammar-pattern links must be set up by you; without them a chapter shows "No grammar patterns linked".
- **Do:** link grammar patterns to chapters (Grammar tab) and put the right chapter on your words; readiness is only as good as that setup.
- **Do:** try adding a test and a result on the phone; editing a saved test or result isn't built yet (delete and re-add).

## Phase 9: WhatsApp capture and reminders

- **Decide:** screenshots are not built, only text. Options: (a) on-device text recognition with ML Kit (free, the image never leaves the phone; but the only React Native package for it is an old native module I couldn't test with this React Native version, it adds roughly 20 MB to the APK and could break the first build); (b) send the image to Gemini (works today, but sends classmates' names and numbers to Google, and Groq can't read images, so no fallback); (c) leave it at text. I chose (c) for now. Phase 11 (exercise scanner) plans to bring on-device recognition anyway, so (a) could be done once and reused here. If you pick (a) or (b), the share target also has to be widened to images.
- **Decide:** reminder defaults: the evening before at 18:00, otherwise the morning of at 08:00, one reminder per task. Right times? Want a second reminder on the day?
- **Decide:** how dates are read. A weekday means the *next* one after today (on a Wednesday, "Mittwoch" is next week); numbers are day-first (12.11. is 12 November); a date with no year is this year unless that was over 60 days ago. If a message was written days ago, "Freitag" may be the wrong Friday: the review screen shows the date for you to fix before saving.
- **Decide:** the plan only includes tasks that have a date, due within a week; urgent ones (2 days, or overdue) go ahead of the grammar item. At most 3 urgent and 2 later ones. Right order and limits?
- **Decide:** the message is never stored, only the tasks you approve. That keeps classmates' data out of the database, but it also means a scanned message can't be re-read from history.
- **Decide:** duplicates are spotted only when an open task has the same title (ignoring capitals). Enough?
- **Decide:** the daily limit for message scans is 10 (`default_daily_cap`). Right?
- **Decide:** names inside a message can't be removed before it goes to the AI (same limit as the sentence coach). Phone numbers, emails, links, @mentions and a pasted "[time] Name:" prefix are. Acceptable?
- **Check:** whether WhatsApp on your phone shows Share (not only Forward and Copy) for a text message, and what text arrives (message only, or with sender and time). The paste route works regardless.
- **Check:** how well the AI finds tasks and copies dates on real class messages (German, English, mixed). The prompt is untested against Gemini and Groq. Try 5–10 real messages; anything it misses or invents is a prompt fix.
- **Check:** the date reader understands full German and English words only. Short forms (Mo, Di, Fr), "next week" with no day, and times of day are not read: you pick the date. Tell me which phrases your teachers use that it misses.
- **Check:** reminder times are worked out in the phone's timezone when you save. If the phone's timezone changes later, saved times don't move.
- **Do:** collect 5 to 10 real, anonymised class messages (German, English, mixed) to test extraction on.
- **Do:** build an APK (`npx eas-cli@latest build -p android --profile preview`; Expo Go can't receive shares) and try the whole route: copy or share a homework message, check the tasks, save, and see the reminder arrive. The target is under a minute. The share target needs native Android code, so it can't be tried in Expo Go.
- **Do:** on your phone, allow notifications for the app and check that battery saving doesn't delay reminders (some makers are aggressive).

## Phase 10: Hardening and v1 release

- **Decide:** how release APKs get built. I set up Expo's free build service (the `production` profile): it has a monthly limit and queues. Building on your Mac needs Android tooling and isn't set up. Which do you prefer?
- **Decide:** what counts as a blocking issue, and when v1 is done. I proposed a definition in [docs/v1-trial.md](docs/v1-trial.md) (anything that stops you studying that day or loses data; the count restarts after one; you decide when v1 is done). Right?
- **Decide:** the privacy limits in [docs/privacy.md](docs/privacy.md): names in running text can't be removed before text goes to the AI or LanguageTool, and the free tiers of Gemini, Groq and LanguageTool are third parties whose terms may allow them to keep what they receive. Acceptable, or self-host LanguageTool / switch it off? Which classmates' names go in `AI_REDACT_NAMES`?
- **Decide:** the free server sleeps when unused and the app now copes (waits up to a minute, wakes it as you open the app). It could be kept awake by pinging it every ~10 minutes from GitHub; that fits the free hours but GitHub's schedule is unreliable and I haven't done it. Worth it?
- **Decide:** crashes in the app itself aren't reported anywhere (Sentry is only on the server; the roadmap's Phase 0 said both). Adding it means another native module in the build. Skip for now, or add after the first build works?
- **Decide:** there is no "delete my data" button. With one learner, deleting the Supabase project does it. Enough?
- **Check:** run the backup workflow by hand once (GitHub, Actions, Database backup, Run workflow) and read the log for `OK:`. Then do one trial restore into a spare free Supabase project (steps in [docs/backup-and-restore.md](docs/backup-and-restore.md)). The workflow and a dump from the real Supabase have never been run; the local round trip works.
- **Check:** the first production build: the three `EXPO_PUBLIC_*` values set with `eas env:create`, an https API URL, and the finished APK's permissions (`aapt dump permissions`). None of this could be tried here.
- **Check:** how Supabase's free plan behaves when unused: it pauses a project after about a week of inactivity and you press Restore in its dashboard. Daily use should prevent it; whether the nightly backup's connection counts as activity isn't known.
- **Check:** the current terms of Gemini, Groq and LanguageTool's free tiers on keeping and using what you send.
- **Do:** keep the signing key (`eas credentials`) somewhere safe: losing it means you can't update the installed app.
- **Do:** go through the first-day checklist in [docs/v1-trial.md](docs/v1-trial.md). It covers every earlier "Do" item on this list.
- **Do:** the two-week daily trial itself.

## Phase 11: Exercise scanner

- **Decide:** the text reader. I chose `expo-text-extractor` (small, readable, MIT, one maintainer) over the old `@react-native-ml-kit/text-recognition` and over writing our own module. Its ML Kit model is the Play-services kind: small APK, but it needs Google Play services and may download on first use. If your phone has no Play services, or the first build fails on it, the alternatives are the bundled ML Kit model (about 4 MB more per script, needs our own thin module) or leaving photos out. OK to keep?
- **Decide:** the camera permission. The release build now asks for the camera (the image picker declares it; the microphone one is blocked). The only alternative is to drop "Take a photo" and keep "Choose a photo" (you would take the photo with your camera app first), which needs no permission. Keep the camera?
- **Decide:** the daily cap is 15 exercise helps (`default_daily_cap`; one use per exercise, repeats are free). Together with 25 sentence checks and 10 message scans the overall limit of 40 AI requests a day can now be reached sooner. Right numbers?
- **Decide:** hint first and answer on tap is how it works (the answer arrives with the hint in one AI call, hidden until tapped, so asking for it costs no extra allowance). The catch: the answer is already on the phone, only not shown. Fine?
- **Decide:** your own attempt goes through the sentence coach, so each "Check my sentence" uses one sentence check. Should it compare with the book's answer instead, or in addition?
- **Decide:** only verb endings can be Confirmed (dictionary-proven). Articles, cases, word order and vocabulary exercises stay "Likely". Worth adding more dictionary checks (article + noun gender, plural forms), or is "Likely" honest enough?
- **Decide:** exercises with more than 8 items are cut to the first 8 (token limit). Split the photo by crop for longer ones?
- **Decide:** screenshots of WhatsApp chats could now be read with this same on-phone reader (the Phase 9 question): the image would stay on the phone, but classmates' names in the text would still reach the AI unless you delete them in the review box. Want that added?
- **Check:** recognition quality on your real book pages: gaps (___ can come out as underscores, dashes or nothing), tables, umlauts and ß, small print, two columns. The review box is how you fix it, but if it is wrong on every page we need a different approach.
- **Check:** how much of each exercise type survives as text. Picture, audio and layout-based exercises won't fully; test whether the AI really says so instead of guessing (the prompt is untested against Gemini and Groq).
- **Check:** whether the AI's answers on real Netzwerk neu exercises are right. A wrong answer labelled Likely is the risk: take 10 and compare with the key in the book.
- **Check:** crop-then-read: Android's crop screen after the camera is part of the image picker and untested here. Also that the photo's cache copy is really deleted (look at the app's storage after a few scans) and that Android reopening the app mid-photo (`getPendingResultAsync`) lands on the text, not an empty screen.
- **Check:** the finished APK's permissions (`aapt dump permissions`): CAMERA expected, RECORD_AUDIO must not appear.
- **Do:** take 5 to 10 photos of typical exercises (no names) and try them through Today → Scan an exercise. The first-day checklist in [docs/v1-trial.md](docs/v1-trial.md) has the steps.
- **Do:** build the APK again (`eas build`), since the camera and text reader are native modules: Expo Go can't test them.

## Phase 12: Allango media inside the app

- **Check (the big one):** does Allango's player work inside the app? On the built APK: open a chapter with an Allango audio link, tap **Play**. Does the page load (no 403 or "access denied"), does the audio play, does it ask you to sign in, and does the sign-in stay after closing the app? If it refuses, the player says so and **Open in browser** is the fallback; tell me what it showed.
- **Check:** does audio keep playing when the screen turns off or you switch app? Nothing in the app can force this: a web view may be paused by Android. If it stops, the options are the phone's browser (which may behave better) or a different approach.
- **Check:** how Allango and Netzwerk neu link things: one link per exercise (as your audio link did), a code printed in the book, or a QR code. That decides whether a scan could jump to the right audio. Still useful: one **video** link, to check the same holds.
- **Check:** the player trusts the saved link's main domain, so a login page on another domain (a Klett or Google sign-in) opens in your phone's browser and the sign-in may not come back to the in-app view. If you hit this, tell me the domain.
- **Decide:** the in-app view keeps Allango's cookies in the app's storage, and signing out of Lumen A1 does **not** clear them (the sign-in to Allango stays until you clear the app's storage). Fine for one phone, or should signing out clear them too (needs one more native module)?
- **Decide:** every https resource link opens in the in-app view, not just Allango's (the rules above keep it on that link's own site). Should it be Allango-only, with other links going to the browser?
- **Decide:** the answer box under the player checks German writing with the sentence coach (one sentence check each). For listening exercises where you pick or tick answers, nothing is checked: only the done tick. Enough for now?
- **Decide:** confirm we only store links and use Allango's own player, never copy their files. (Built that way; this is your sign-off on the copyright reasoning.)
- **Do:** rebuild the APK (the web view is a native module: I haven't tried it in Expo Go), add an Allango audio and a video link to a chapter, and go through the new steps in [docs/v1-trial.md](docs/v1-trial.md).

## Improvement work (2026-11-11 to 12): reliability, accuracy, readiness

The three phases in [ROADMAP.md](ROADMAP.md). Its section 6 has the full list with the reasons; this is the short form, in the same Decide / Check / Do terms as the rest of this file. As agreed, each Decide item has a default already built.

- **Do:** fill in the empty settings: `SUPABASE_URL` and `DATABASE_URL` in `backend/.env`, and all three values in `app/.env` (ROADMAP section 6.2 says where each comes from). The backend refuses to start without the first two, and says so.
- **Do:** put the work into git: `sh scripts/snapshots-to-git.sh --dry-run`, then without `--dry-run`. I could only dry-run it: commits need your approval on this machine.
- **Do:** the new phone checks in [docs/v1-trial.md](docs/v1-trial.md): typing on every screen, the scanner on real book pages, the umlaut tip.
- **Do:** push to GitHub once and look at the CI run: it now also builds the Android bundle, and the workflow has never run.
- **Check (most likely to need a second pass):** does the field you type in stay above the keyboard on every screen? Built from Expo's current guidance, never seen on a phone. Note any screen with a covered field or an empty gap above the keyboard.
- **Check:** the photo clean-up on real pages. Are gaps, ß and `Ich` right, and did it ever change something that was correct in the book? The rules were written from typical misreads, not from your book.
- **Check:** the "a lot of this looks misread" warning: does a bad photo get it, and does a good photo ever get it? The line is 3 or more odd words and at least 15% of the words: a guess until real photos say otherwise.
- **Check:** TalkBack reads each field with its label and speaks errors as they appear (only if you use it).
- **Check:** the Gemini request itself. It is unchanged, but no usable key existed to test it.
- **Decide:** the Gemini key answers 402 (prepaid billing, no credit). Default: left in place, skipped for ten minutes at a time with one log line. Replace it with a free-tier key or delete it?
- **Decide:** the backup Groq key is used as a second provider. If it is a second account only to get round rate limits, that may be against Groq's terms. Keep, or remove?
- **Decide:** photos are read on the phone, not by a cloud vision model (free, private, works offline; less accurate). Default: stay on the phone unless real photos prove unusable.
- **Decide:** keyboard handling uses React Native's built-in view rather than `react-native-keyboard-controller` (one more native library). Default: built-in, and switch only if the phone test shows fields still covered.

## Community forum (2026-11-12): one group chat for everyone with an account

You asked for one group chat where everyone who has access can ask and answer, text only, working for about 30 people at once, and for the keyboard problems to be fixed. Built: the backend (`backend/app/community/`), the chat screen reached from a card on Today, and keyboard fixes on every screen with an input. README has a "Community forum" section; `docs/privacy.md` and `docs/v1-trial.md` were updated. As agreed, each Decide item already has a default built.

- **Do (important): how do 30 people get accounts?** Sign-up is invite-only and the app has no sign-up screen, so each account is made by hand in the Supabase dashboard (Authentication → Users → Add user), and each person then gets their email and password from you. For 30 people that is slow. Options: keep it (safest), or add invite codes or a sign-up screen (a real feature: abuse, email confirmation, a reset-password flow). Nothing was built.
- **Do:** set `COMMUNITY_MODERATOR_EMAILS` on Render to the emails of whoever should be able to delete other people's messages. With it empty only authors can delete their own messages.
- **Do:** test on two phones (the chat section in `docs/v1-trial.md`). **Nothing in the chat has been seen on a phone**: no emulator exists on this Mac.
- **Do:** rebuild the APK before testing the chat: this app has never been built, so this is the first build anyway. The chat adds no new native library.
- **Check (important): is the free server fast enough for 30 people?** Measured here: 30 people each posting about once a second, a send took 14 ms at the median and the message reached the other 29 phones 1 ms later, all 9,000 deliveries arrived once and in order. That was a laptop with a local database; Render's free plan has much less CPU and a network hop to Supabase. Not measured there.
- **Check:** does an open chat keep Render's free server awake? It sleeps after about 15 quiet minutes and takes up to a minute to wake. An open WebSocket may or may not count as activity. The chat copes either way (it reconnects and catches up) but the first message after a sleep would be slow.
- **Check:** the AI limits were sized for one learner. Per-person limits still hold, but the shared daily ceilings (Groq 800 requests a day) are now shared by everyone using the app.
- **Check:** the database pool is 5 connections (`backend/app/core/database.py`). Fine for the chat in the load test, untested for 30 people using the whole app at once.
- **Decide:** voice messages are **not built**, although you said "maybe, if it is easy to manage". They are not easy here: they need file storage (the free stack has none set aside), the microphone permission (deliberately blocked in `app/app.json`, and `docs/privacy.md` promises the app can't record), upload and playback, and a way to moderate audio. Default: text only. If you still want them, the likely route is short clips in Supabase Storage with a size cap and a moderator delete.
- **Decide:** one room, not channels. Replies quote the message they answer, which keeps questions and answers readable when 30 people talk at once. Default: one room; add channels (e.g. by chapter) only if the room gets too noisy.
- **Decide:** a person's name in the chat is a display name they choose (unique), never the email. Default as built. Anyone can change it later, and old messages show the new name.
- **Decide:** limits: 2,000 characters a message, 20 messages a minute per person. Default as built.
- **Decide:** deleting: anyone can delete their own message (the text is erased from the database), moderators anyone's. No editing. Default as built.
- **Decide:** nothing is built for: an unread badge, push notifications for new messages, typing indicators, report or block, message search. Default: none. Report/block is the one to reconsider before inviting people you don't know: today a moderator can only delete after the fact, and cannot stop a person.
- **Decide:** how long messages are kept. Default: forever, nothing prunes them. The nightly backup includes them (see `docs/privacy.md`).
- **Decide:** "Copy" on a message is "Share or copy", which opens Android's share sheet (it has a Copy button). A direct Copy needs `expo-clipboard`, one more native library. Default: no new library.
- **Decide:** the chat is a stack screen opened from Today, not a seventh tab (the tab bar is full, and a stack screen has no tab bar under the input, which keeps the keyboard handling simple). Default as built.
- **Check (keyboard):** the fixes follow Expo's current guide (`KeyboardAvoidingView`, `padding`) but were never seen on a phone. On Android the input jumps up after the keyboard has finished opening instead of sliding: that is how this component works. If it feels bad, `react-native-keyboard-controller` slides it smoothly but needs Reanimated, a provider and a development build. Not added without your say-so.

## Restyle, step 1 (2026-11-13): theme tokens, light and dark

Built the first step of the approved restyle: the glass color tokens for light and dark in `app/src/ui/theme.ts`, a theme provider (`app/src/ui/ThemeProvider.tsx`), and every screen now reads its colors from the active theme. The screens still look like the old layout, only in the new colors: glass cards, the Nunito font, icons, the new tabs and drawer, and the new Today screen are the next steps.

- **Do:** dark mode needs a new APK build: Android ignores the light/dark setting without `expo-system-ui`, which is native. In Expo Go the app follows the phone already.
- **Check:** with the soft new page color (#EEF0F8) and translucent cards, screens that are not restyled yet may look flat until the glass card and backdrop arrive (step 2). Expected, not a bug.
- **Decide:** the chat name colors were not in the approved tokens; I picked eight per theme, checked at 5.4:1 or better on both bubble colors. Default as built.
- **Decide:** the drawer's Dark mode switch will set light or dark and remember it on the phone; "follow the phone" is the starting value. Default as built (the switch itself comes with the drawer).
- **Decide:** an outline of a card or list row now uses the soft glass edge, not the 3:1 control edge; inputs, chips, checkboxes and answer buttons keep the 3:1 edge (the audit only asks it of controls). Default as built.

## Restyle, step 2 (2026-11-13): shared components, font, glass

Built: Nunito in four weights for the whole app (`app/src/ui/fonts.ts`, loaded before the splash screen hides), the app's own `Text`/`TextInput` (`app/src/ui/Text.tsx`: app font and theme text color by default, so nothing stays black in dark mode), the glass layer (`app/src/ui/glass.tsx`: `Backdrop` with soft color patches, `Glass` card with expo-blur), and restyled buttons, inputs, chips, cards, progress bar and spinner (`app/src/ui/components.tsx`). Every font size is now on the type scale (13 smallest). Glass is ready but no screen uses it yet: the Backdrop goes in with the new navigation (step 3), and the glass cards with the Today and Words screens.

- **Do:** expo-blur, react-native-svg, expo-font and expo-splash-screen are native: a new APK build is needed (all four are in Expo Go, so Expo Go works too).
- **Check (on the phone):** the blur strength (`intensity={40}`, the design said "blur 24" in CSS terms, which has no exact Android equivalent) and whether the blur over already-soft patches is worth its cost. If it looks the same as no blur, the fallback (translucent fill only) is cheaper.
- **Check:** the primary button's shadow is drawn by React Native's `boxShadow`, new in recent versions. Not seen on a phone.
- **Decide:** chips are 40dp tall with a 48dp touch area (Material 3's pattern) rather than 48dp tall. Default as built.
- **Decide:** `Card` is flat unless a screen asks for `glass`, so the 70 existing cards are flat sections, following the "only the main card and the plan list carry glass" rule. Default as built.
- **Decide:** progress bars are now the primary indigo instead of green (green is kept for "done"). Default as built.

## Restyle, step 3 (2026-11-13): icons, five tabs, drawer

Built: Lucide vector icons everywhere a glyph or emoji was used as an icon, the five tabs (Today, Course, Review, Words, Write) on a glass bottom bar with a pill on the active tab, and the left drawer opened by ⋮ on Today (Grammar; Scan an exercise; Class tasks from WhatsApp; Community chat; Account and daily reminder; Dark mode). Community, Scan and the class-tasks card left the Today screen.

- **Decide:** icons are Lucide, not `@expo/vector-icons`: Expo's icon guide now says `@expo/vector-icons` will be deprecated, and Lucide draws with react-native-svg (already in the app, no native code, works in Expo Go). One family throughout. Default as built.
- **Decide:** the drawer is the app's own (React Native's Modal and Animated), not Expo Router's Drawer, which needs Reanimated and Gesture Handler and would wrap every screen. Trade-off: no swipe from the screen edge to open it, only the ⋮ button (as approved). Default as built; Reanimated comes with the engagement layer, and the swipe can be added then if you want it.
- **Decide:** tab icons: Today = sun, Course = open book, Review = repeat arrows, Words = "A" book, Write = pen. Drawer: Grammar = spell-check, Scan = scan-text, Class tasks = clipboard, Community = speech bubbles. Default as built.
- **Decide:** the Dark mode switch also offers "Follow my phone's setting" once you have flipped it, so you can go back to automatic. Default as built.
- **Check (on the phone):** the tab bar's look (pill size, label spacing, 80dp height above the gesture bar), the drawer's slide and scrim, and the streak pill. None of it has been seen.
- **Check:** only the tab screens have the colored backdrop; the screens opened on top (chapter, word, grammar, chat…) keep a plain page until they are restyled, because see-through pages overlap during Android's screen transition.

## Restyle, step 4 (2026-11-13): the Today screen

Built: Today in the approved layout. A glass main card (greeting by time of day, the book-and-"Hallo!" picture, a progress ring with done/total, "About N minutes left", one primary Continue button), then flat sections: four numbers (day streak, cards due, words known, chapters), the Monday-to-Sunday week strip, one badge row, the plan in a glass card (48dp checkboxes, grey "N min"), and the next test with its readiness bar. Backend: the dashboard now sends `on_track.week`, the days studied since Monday (pure `week_studied` in `dashboard/progress.py`, tested).

- **Decide:** Continue opens the first plan item that isn't done and is labelled with it ("Continue: Review 18 cards"). When everything is done the button goes and the card says "All done for today. Gut gemacht!". Default as built.
- **Decide:** there is no badge or XP system yet, so the badge row follows plain rules from numbers the app already has: a streak milestone (3, 7, 14, 30, 60, 100, 200, 365 days) reached with today's study shows as "New badge"; otherwise it shows the closest next goal ("Next badge: 7 days in a row · 2 more days to go · 5/7") across streak, words known (10 … 1000) and chapters done (1 … 24, capped at the course's count). The approved preview's grey "+50 XP" is left out until XP exists; stored badges, XP and the celebration animation belong to step 6 (engagement layer). Default as built.
- **Decide:** "Where am I weak?" left Today (the approved layout has no such section). Weak grammar still reaches the plan as its own item, weak words are in the Words tab, and the mistake log is still linked from the grammar screens. Say if you want a weak-spots row back on Today, or a mistake-log entry in the drawer.
- **Decide:** "words known" counts the words at the top learning stage (what the old screen called "words mastered"). Default as built.
- **Decide:** the on-track label ("On track" / "Slipping") is gone as a separate badge; its one-sentence reason is the line under the greeting. Default as built.
- **Check (on the phone):** the glass main card and plan card blurring the backdrop (two live blurs on one screen), the picture's "Hallo!" sitting inside its bubble, the ring, and the week strip's spacing on a narrow screen. None of it has been seen.
- **Check:** plan items the app ticks itself (reviews, writing, grammar) show a box with no edge, and only the boxes you can tick have the 3:1 edge. See whether that reads clearly, or whether app-ticked items should show no box at all.

## Restyle, step 5 (2026-11-15): Review tab, review cards, Words tab

Built: the Review tab (glass "Today's cards" card with the one Start button, then flat sections), the review session card (glass, tinted rating buttons and feedback strip, der/die/das buttons on the article card), and the Words tab in the approved layout: "Which article?" quiz, colour key, search, All/der/die/das filter and one rounded word list. Add word moved to a + in the header.

- **Decide:** the article quiz is practice only. It asks up to ten of your own nouns per round (nouns with an article that are not plural-only) and does not change any word's review schedule or stage; the Review tab's cards do that. Say if a right or wrong answer here should also count towards the word's schedule. Default as built.
- **Decide:** a round is ten random nouns with a score at the end and "Another round" (the preview looped forever). If you have fewer than ten nouns, the round is all of them. The quiz is hidden until you have saved at least one noun with an article. Default as built.
- **Decide:** the word list no longer shows the learning stage (New, Learning, Mastered), as in the approved layout; it is still on the word's own screen. The chapter screen's word list uses the same rows, so it lost the stage too. Say if you want it back as a small grey label.
- **Decide:** words with no article (verbs, adjectives, phrases) show their word type ("verb", "adj.") in the first column instead of an article; plural-only nouns show "plural only" on the right. Default as built.
- **Decide:** the filter only filters by article, so choosing der/die/das hides verbs and other words with no article; "All" shows everything. The search box still searches everything and combines with the filter. Default as built.
- **Decide:** the rating buttons on review cards are tinted (Again red, Hard orange, Good green, Easy indigo) and keep their words, so color is never the only signal. Default as built.
- **Decide:** the review session screen has its own colored backdrop (it is opaque, so it does not overlap during the screen transition). Default as built.
- **Check (on the phone):** the quiz buttons' fill when right (white or dark ink on the article color), the red edge on a wrong pick, the Next button inside the feedback strip on a narrow screen, the four rating buttons' labels ("Not right" on the sentence card is the longest), and the glass quiz card plus the Backdrop behind a scrolling list. None of it has been seen.
- **Check:** the word list is one rounded block made from separate rows (not a single blurred glass card, so a long list scrolls smoothly). See whether its see-through look matches the quiz card above it.

## Restyle, step 6 (2026-11-15): the engagement layer (first part)

Built: Reanimated 4.7.1, react-native-worklets 0.13.0 and expo-haptics 58.0.8 (installed with `npx expo install`; all three are in Expo Go, no config needed, the Babel plugin is automatic). Today's progress ring now sweeps to its value when Today opens and whenever it changes. The right der/die/das answer pops (and gets the tick), a wrong pick shakes, and the feedback strips (quiz and review cards) fade in. A perfect article-quiz round and a finished review session play a one-off burst of colored specks with a success buzz. A badge earned today pops once when Today opens. Everything that moves is skipped when Android's "Remove animations" is on (the buzz and the words still say it went well).

- **Decide:** haptics are for real wins only: a finished review session and a perfect quiz round. Not on every correct answer, not on wrong ones. Default as built.
- **Decide:** at most one or two things move per screen (the skill's rule): Today = the ring, plus the badge when there is a new one; quiz = the answer button, plus the feedback strip; session done = the burst. Default as built.
- **Decide:** XP, stored badges and "+50 XP" are NOT built. They need new backend tables, a rule for what earns XP, and a stored "already celebrated" flag; none of it is in the approved preview except the grey "+50 XP". Today's badge row keeps its plain rules (a streak milestone reached today, else the nearest goal). Say if you want XP and stored badges, and what should earn them.
- **Decide:** no Lottie (it is not in Expo's SDK 58 list, so it needs a development build and its license page could not be loaded) and no unDraw illustrations beyond the Today picture already built. The one-off burst is drawn with Reanimated. Default as built.
- **Decide:** the drawer still opens only by the ⋮ button; no swipe from the edge (it needs react-native-gesture-handler, which is not installed). Say if you want the swipe.
- **Decide:** the streak pill has no animation yet; there is no stored "streak went up" event to react to. Comes with stored badges and XP if you want them.
- **Check (on the phone, Expo Go):** the ring sweep, the pop and shake feeling short and not silly, the burst not clipped at the card's edges (it plays inside the glass card), the buzz strength, and that "Remove animations" really stops all of it. None of it has been seen.
- **Check:** the next APK build includes Reanimated and Haptics (native code); Expo Go already has them.

## Restyle, step 7a (2026-11-15): the screens opened on top of the tabs, first batch

Built: every screen opened on top of the tabs (everything in the Stack, not the five tabs) now sits on the colored backdrop and has a plain solid header with the app font (done once in `(app)/_layout.tsx`: `screenLayout` wraps each screen in its own opaque `Backdrop`; the tabs keep theirs). New shared pieces in `ui/components.tsx`: `Card` can be a button (`onPress`, with a ripple), `SectionTitle`, `Pill`, `TextLink` (48dp). Restyled by hand: the Course and Write tabs (they were still on the old look), the chapter screen, the word screen, Grammar (list, rule screen, practice), the shared practice session (also used by the sentence lessons), the Pronounce button and the mistake rows.

- **Decide:** one glass card per screen, chosen by a plain rule: Course = the first chapter not completed; Write = the first lesson with exercises you have not started ("Up next"); Grammar list = the weakest rule; the chapter, word and rule screens = their header card; practice = the question card and the score card. Everything else is flat. Default as built.
- **Decide:** the chapter's resource tick box is now 48dp like the plan's (it was 28dp), and the "Play"/"Open" links, "Show a hint" and the Grammar "Practise" button are 48dp to touch. Default as built.
- **Decide:** a word's article is colored on the word screen's headword (der blue, die red, das teal), and its stage is a pill (Mastered is green with a tick). Default as built.
- **Decide:** practice answers show a tick or cross as well as green or red; the question's result strip fades in; a practice round with 90% or more right plays the same burst as the review session. Default as built.
- **Decide:** the stage-by-stage header of the stack screens is solid (the page color), not see-through. The backdrop's colored patches start just below it. Default as built.
- **Check (on the phone):** the seam between the solid header and the first colored patch under it (top left, on screens with a header), that the slide transition between two stack screens shows no ghosting, the "Up next"/current glass card on Course and Write, and the practice screen with the keyboard open (the backdrop does not move).
- **Still on the old look (next batch):** Tests (exams), Class tasks (capture), the scanner, Community, the resource player, the mistake log, Account, the add/edit forms (word, chapter, resource, test, mistake) and sign-in. They already have the new colors, font and icons, the backdrop and header, but not the hand-made layouts.

## Restyle, step 7b (2026-11-15): the screens opened on top of the tabs, second batch

Built: Tests (list and detail), Class tasks (list and add-from-message), the exercise scanner, the Community chat (touch targets and colors only), the resource player, the mistake log and mistake screen, Account, the add-word dictionary lookup, the word/chapter/resource/test/mistake forms and sign-in. New helper `toneAccent(colors, token)` in ui/theme.ts turns a status color (success, warning, danger…) into a pill's tinted pair; `TextLink` can be `tone="danger"`; `icons.ts` gains ChevronLeft.

- **Decide:** one glass card per screen again: the next test, the first open class task, the intro or exercise card on the scanner, a mistake's header, the Account top card, a word's summary in the add-word form, the sign-in form (the sign-in screen now has the colored backdrop too). Default as built.
- **Decide:** Community is left as it was apart from 48dp touch targets ("Change name", cancel reply, "New messages") and the app colors: the chat was finished and tested, and its bubbles, composer and day chips already use the theme. Say if you want the bubbles restyled too.
- **Decide:** the resource player keeps its exact layout and gestures. The grab handle row and the three page buttons are now 48dp tall (the sheet's resting bar grows from 80 to 96dp, all from the two constants), "‹ Back in page" uses a chevron icon, and the sheet's shadow uses the theme. Check it with the web player on the phone: it is the screen I can least test.
- **Decide:** in the word forms the article is chosen with the same colored der/die/das buttons as the quiz, and the dictionary results ("Use this") are tappable cards. Default as built.
- **Decide:** the test verdict ("Looking ready", "Almost", "Not ready") is a tinted pill with its words; the Scanner's answer label (Confirmed, Likely…) is the same kind of pill. Default as built.
- **Check (on the phone):** the player's page and bar (its sheet height changed), the chat on the new header, the glass cards on the scanner with the keyboard open, and sign-in with the new backdrop.

## Restyle, step 8 (2026-11-15): the pre-delivery checklist

Ran the ui-ux-pro-max skill's pre-delivery checklist (`references/pro-rules.md`) as far as it can be run without a phone: a contrast script over both palettes (text on the page, flat, glass, nav and sheet, each over the strongest spot of all four backdrop patches), a scan of every `Pressable`, a search for hard-coded colors, emoji and glyph icons, the reduced-motion paths, and the bottom safe area. Fixed what it found.

**Found and fixed**
- Pressed feedback was missing on the Today "Add a test" link (now `TextLink`), the resource-kind buttons, the player's grab handle, and the mistake form's word suggestions; the chapter's long-press-to-delete rows had no screen-reader way to delete (they now offer a "Delete this resource" action).
- The player's sheet slid even with "Remove animations" on; it now jumps.
- Eleven screens opened on top of the tabs (chapter, word, grammar x2, mistakes x2, tests x2, class tasks, account, session done) used a plain `ScrollView`/`FlatList`, so the last button could sit under Android's navigation bar. They use `FormScroll` (or the new `useBottomInset()`), which leaves that space.
- Five text fields had only a placeholder (review answer, sentence and correction, verb forms, word search in the mistake form): they now have an accessible name.
- The bottom tab labels (12dp, in a fixed-height bar) no longer grow with the system text size; the "Hallo!" in Today's picture does not either (it sits in a drawn bubble). Everything else scales. The quiz answer buttons and the chat send button are minimum heights now, not fixed.
- Icons: named sizes (`ICON.large/bar/mark/inline/badge/small`, no loose numbers) and one stroke width (Lucide's default; only tick and cross marks are heavier).

**Passed**
- No emoji or text glyphs as icons (the "→" and "•" left are punctuation in sentences), no hard-coded colors outside `ui/theme.ts`.
- Contrast: all text pairs are 4.5:1 or better in both themes on the page, flat sections, glass cards, nav bar and sheet, except two spots measured at the exact middle of a backdrop patch: a bare primary link over the top-left patch in light mode (4.10:1; it is 4.5:1 once 30% of the patch's strength has faded, a few dp away) and pink text in dark mode (4.09:1; pink is never used as text, only in drawings). Control edges are 3:1 against their own fill in both themes; the drawer scrim leaves text at 13:1 (muted 6.8:1).
- Every tappable element is 48dp or more (the filter chips are 40dp with a 4dp hit extension each side), has a ripple, and icon-only buttons have names; selected, checked and expanded states are exposed.
- Color is never the only signal (ticks, crosses, words and pills go with every color); the sheet and drawer have button alternatives to dragging; sign-in allows password managers and paste.

**Not checkable here, needs your phone**
- Dynamic Type at the largest size (look for clipped text on Today, the quiz and the tab bar); "Remove animations" turned on (nothing should move: ring, pop, shake, burst, drawer, sheet).
- Dark mode on every screen (the colors are measured, the look is not seen); the seam under the solid header; blur performance on the glass screens (the quiz, the review session, Today) on your phone.
- The small phone (360dp wide): the four rating buttons, the three quiz buttons and the Today numbers row.
- Landscape and tablets are out of scope: the app is portrait-only and for phones.
- TalkBack order on Today and the quiz.

## Change after step 8 (2026-11-15): Review and Community swap places, stronger drawer

At your request: **Community** (the group chat) is now the third tab of the bottom bar (speech-bubbles icon), and **Review** is the first row of the left drawer under Study (above Grammar). The drawer's "Together" group is gone, since the chat was its only row. The drawer panel is also more solid: 94% opaque instead of 86% in light mode and 88% in dark.

- **Decide:** Review is now a normal screen opened on top of the tabs (same address, `/review`), so its back button returns to where you came from (Today, or the drawer's screen), and "Start" still opens the session. Today's "Continue: Review N cards" opens it the same way. Default as built.
- **Decide:** the bottom bar now hides while the keyboard is open, on every tab (it did not before). With the chat in a tab, this keeps the message box right above the keyboard instead of leaving a gap the height of the bar. Default as built.
- **Decide:** Today's progress still counts reviews in the plan; nothing about how cards are scheduled or answered changed.
- **Check (on the phone):** typing in the chat with the bar hiding and returning, "Change name" in the chat's header (it is set from inside the screen, now a tab), the tab bar's five labels (Today, Course, Community, Words, Write), and that the drawer now reads clearly over a busy page.

## Ask the Community (2026-11-15)

Built at your request: an "Ask the Community" link next to words, exercises, chapters, grammar rules and course materials. It opens a sheet with the item as a card, four quick prompts and a question box, and posts to the group chat, where the card shows above the question and people answer with the normal reply. Your choices: a **card** (not plain text), **all four kinds** of material, and **short excerpts** of course text allowed.

Where it is: the word screen; every practice exercise (grammar practice and the sentence lessons, with your answer once you gave one); each scanned exercise item (with what you typed); the chapter screen (the chapter); the grammar rule screen; the resource player's bottom bar (with your answer).

- **Decide:** the sheet stays on the screen you were on instead of jumping to the chat, so a practice round or a scanned exercise is not thrown away; after sending, "Open the chat" goes there. Default as built.
- **Decide:** NOT in the review session, the Words article quiz, the mistake log or the Today plan in this first version (the review session is a timed, focused flow, and every card in it is a word you can also ask about from its word screen). Say if you want it there too.
- **Decide:** a card is plain text the asker's phone wrote: no link, no id, nothing another phone opens, so a classmate can't tap through to your word or exercise. Course resources share their name and page ("Kapitel 4 · Audio · S. 24, Ü 3"), never the Allango link. Grammar rules share a 220-character excerpt; the server caps any card at a 120-character title and 6 lines of 300.
- **Decide:** the question itself is required (the chat refuses an empty message); the quick prompts write a starting sentence into the box. If you have no chat name yet, the sheet asks for one first.
- **Decide:** the chat's "Share or copy" on a question shares only the question text, not the card.
- **Check (on the phone):** the sheet over each screen with the keyboard open, the card in the chat bubble (yours and others'), and TalkBack reading the card as one sentence.
- **Backend:** new nullable `attachment` column on `community_messages` (migration `c4a8e2f61d93`): run `alembic upgrade head` on the real database before the new app version is used, or posting a question with a card fails.
- **Changed (2026-11-15, your request):** the speech-bubble button left the chapter's resource rows (Play is back at the end of the row). In the resource player the bottom bar is now four compact controls: "‹ Back", a reload icon, the Ask the Community icon and "Open ↗" (in the browser, last); the Ask link inside the player's sheet was removed so there is one way to ask there. Reload and Ask are icons only, with spoken labels for TalkBack. The chapter screen keeps its one "Ask the Community" link for the chapter as a whole. **Check:** the four controls fit on a narrow phone.

## Sign-up, forgot password and usernames (2026-11-16)

Built: open sign-up (email and password, email confirmation required), "Forgot your password?" (a code is emailed and typed into the app, then the new password), and one **username** asked on first sign-in (3 to 20 letters, numbers, underscores; reserved names like `admin`; unique; fixed once chosen) that the chat now uses. The chat's "Change name" is gone. Backend 786 tests, app 123 tests, typecheck and lint clean, the Android bundle builds. Not seen on a phone.

- **Do (Supabase):** Authentication → Emails → Templates → **Reset Password**: put `{{ .Token }}` in the body, or "Forgot your password?" sends an email with no code. Sign-up needs "Allow new users to sign up" and "Confirm email" on, and the Brevo SMTP sender (done).
- **Do:** rebuild the APK; the sign-up and username screens have never been on a phone.
- **Check:** does Brevo's mail from a Gmail sender address reach inboxes (not spam) for Gmail, Outlook and Yahoo recipients? If not, a domain you own fixes it.
- **Decide:** Google sign-in is **not built**. Google would need the consent screen published, which needs a domain you own (shared hosts like netlify.app are refused). In Testing mode it would only work for Gmail addresses added by hand (up to 100). Add it when you have a domain.
- **Decide:** usernames are fixed. A moderator can change their own, but there is no screen for a moderator to rename someone else (needs report/block/suspend tools; next step with the chat work).
- **Decide:** the username is asked on first sign-in for everyone, including people who already had a chat name (they keep it and are not asked).
- **Check:** sign-up is open, so strangers can use the shared daily AI limits (Groq 800 a day). Per-person limits still hold. Suspending an account is done in the Supabase dashboard for now.
