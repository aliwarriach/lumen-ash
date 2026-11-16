# Data privacy review

The rules this project set itself: **recordings stay private, and no classmate data is stored.** The one exception is the community chat (below), where people choose to write to each other. This page says what the app actually keeps, who else receives what, what was checked, and what is still open. Facts marked *(checked)* were verified in code or by a test when this was written (Phase 10); the rest are claims about other companies you should read for yourself.

## Short answer

- **Recordings:** the app can't make any. It has no microphone permission *(checked: the built manifest has none, and `expo-audio` is set to playback only)*. It also has no location, contacts or storage permission in the release build. **Since Phase 11 it does have the camera permission**, only to photograph exercises (see below).
- **Classmate data:** the app never stores a class message. Only the tasks you approve are saved, with the text you saw and edited *(checked: a test scans a message, saves its tasks and runs a writing check, then searches every text column of every table for the sender's name, the phone number and the email, and finds none)*. Names inside a message body can't be removed automatically, so check the text before you press **Find tasks**; that text is what goes to the AI.
- Everything is **yours alone**, except the community chat: every row carries your user id, and a test checks that other users can't read or change it. Chat messages are the one thing every signed-in person can read.

## What is stored, and where

**On the server (Supabase Postgres)**

| Data | Contains |
|---|---|
| Course, words, review cards and answers, grammar evidence, mistakes | Your own study records. Mistakes hold the sentences you wrote and their corrections. |
| Sentence-coach checks | The text you submitted **after** phone numbers, emails, links and listed names were removed, and the corrections. |
| Class tasks | Title, kind, date, optional link and reminder time of tasks you approved. Never the message. |
| Tests and results | Test names and dates, scores you entered. |
| AI usage | Counts per day and feature, no text. |
| AI answer cache | The AI's answers, keyed by a hash of the (redacted) request, so repeats are free. **Deleted after 30 days unused** *(checked: test)*. |
| Dictionary | Public Wiktionary data (CC BY-SA). Not personal. |
| **Community chat** | The username you chose (fixed once chosen), and your messages **as you wrote them** (with who answered whom). **Every signed-in person can read all of it**, whoever wrote it. Other people see your username, never your email. Deleting a message erases its text from the database (a row stays, saying it was deleted). Messages are kept until deleted; nothing prunes them yet. **Ask the Community** adds a card to a question with what it is about, as text: a word with its meaning and example, an exercise with your answer if you gave one, a chapter, a grammar rule (a short excerpt) or a course resource (its name and page, never its web link). Short excerpts of course material therefore become readable by everyone in the chat. Deleting the question erases the card too. |

Supabase itself holds your login email and password hash.

**On the phone (app-private storage)**: the saved sign-in, the last Today plan and review queue (kept up to 24 hours so they work offline), review answers waiting to upload, ticks for listening/speaking, and the reminder settings. **Signing out removes all of it and cancels the scheduled reminders** *(checked in code)*. Android's cloud backup is off, so none of this is copied to a Google account *(checked: built manifest `allowBackup="false"`)*. Reminder notifications show the task title on the lock screen unless you hide notification content in Android settings.

## What leaves your server, and who gets it

| To | What | Why |
|---|---|---|
| **Gemini / Groq** (AI) | The sentence to explain plus the grammar findings; or the class message text; or the exercise text you reviewed (Phase 11). Both with phone numbers, emails, links, @mentions, a "[time] Name:" prefix and names listed in `AI_REDACT_NAMES` replaced. Never your history, email or user id. | Explanations, practice, finding tasks |
| **LanguageTool** (public API) | The sentence you wrote, redacted the same way; and the AI's filled-in answer sentences from the exercise scanner | Finding grammar mistakes |
| **Sentry** (if you set `SENTRY_DSN`) | Error reports: a stack trace and the request's URL. **Not** the request body and **not** local variables | Noticing crashes |
| **Supabase, Render** | Everything the app stores, in transit and at rest | Hosting |
| **GitHub** | A **full nightly copy of the database**, kept 30 days as a workflow artifact | Backups |

Fixed in Phase 10: Sentry's default would have attached the request body (up to 10 KB) and the local variables of each stack frame to every error report, even with `send_default_pii` off. That would have put pasted class messages and your sentences, with other people's names, into Sentry. Both are now off and a test crashes a request that carries a secret and checks nothing of it reaches Sentry *(checked; the old settings did leak it)*. The only logging in the backend is provider names, error types and counts, never text *(checked)*.

## Limits you should know

- **Names in running text can't be detected.** German capitalises every noun, so "Tisch" and "Tom" look alike. The redaction removes what has a clear shape (numbers, emails, links, mentions, the WhatsApp sender prefix) and the names you list. Review the text box before sending, and add classmates' names to `AI_REDACT_NAMES` in the backend settings.
- **LanguageTool and the AI companies are third parties.** The free public LanguageTool API and the free tiers of Gemini and Groq have their own terms, which may allow them to keep or use what they receive. **Check their current terms** and decide whether you are comfortable; the alternative for LanguageTool is to self-host it or switch it off (`LANGUAGETOOL_URL=`), and AI is optional.
- **The GitHub backup holds everything.** Keep the repository private and the `SUPABASE_DB_URL` secret secret.
- **No "delete my data" button.** With one learner, deleting the Supabase project erases everything (and the GitHub artifacts expire after 30 days, or can be deleted by hand).
- **Photos of exercises (Phase 11)** are read **on the phone** with Google ML Kit text recognition: the image is never uploaded, and the app deletes its cache copy as soon as the text is read *(written and type-checked, but not yet run on a phone: confirm in the trial that the app's cache doesn't fill with photos)*. A photo chosen from the gallery is copied to the cache first and only that copy is deleted, never your original. You see the text and can delete names before anything is sent; only that text goes to the AI. **Nothing from the scanner is stored on the server**: not the photo, the text or the answers *(checked: a test)*. The ML Kit model comes with Google Play services (the "unbundled" kind), which may download or update it on the phone. The one place a photo's content could linger is the AI answer cache, which holds the AI's answer for 30 days, not your text.
- **Allango in the app (Phase 12):** a chapter link opens in a web view inside the app. Allango's page and your sign-in to it are Allango's business, not ours: its cookies and stored data stay in the app's private web storage, and signing out of Lumen A1 does not clear them. The app never reads the page's content. It only stores the link you saved. The view can't open the phone's files or pop-up windows, and it stays on the saved link's own site (other sites open in your browser).
- **Screenshots** of chats still aren't read. If that is added later it must not send images to a cloud AI without a decision, because pictures of chats show everyone's names. (Phase 11's on-phone reader could do it without sending the image anywhere; see OPEN_QUESTIONS.md, Phase 9.)
- **Community chat:** nothing typed there goes to an AI or to LanguageTool (the chat has no checking), and Sentry's reports carry no request bodies. The nightly GitHub backup **includes the messages**, including ones deleted since the backup was made (the backup is kept 30 days). Nothing stops someone writing a phone number or a name into a message; there is no report or block button yet, and moderators (`COMMUNITY_MODERATOR_EMAILS`) can delete any message. The chat is not kept on the phone, so signing out has nothing of it to clear. Every account in the app can read it, so people you give an account to can read what was written before they joined.
- **Several learners:** the AI answer cache is shared between users (it holds no user id). Fine for one learner; worth a second look now that sign-up is open (anyone with a confirmed email can use the app and the shared daily AI limits).
