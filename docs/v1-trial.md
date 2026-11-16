# v1 trial and phone checklist

Phase 10's goal: **the learner uses the app daily for two weeks with no blocking issues.** Nothing on this page can be done by the code; it is the test the code has to pass. The earlier phases were only ever checked on a computer (they type-check, lint, bundle and pass automated tests), so this is also the first time most screens run on a real phone.

## Part 1: the first-day checklist

Do these once, on the phone, with the release APK ([INSTALL.md](INSTALL.md)). Write down anything that doesn't match what is described.

**Start**
- [ ] Sign in. Wrong password shows a message (not a crash).
- [ ] Today opens within a minute (the first open after a quiet day can wait for the free server to wake; it says so after 8 seconds).
- [ ] Account: shows your email, **Server: Connected**, and the AI allowance ("N sentence checks left today").

**Words and course** (needs the dictionary loaded: see README)
- [ ] Words → add "Tisch": article, plural and audio fill in without AI.
- [ ] Add a verb (e.g. "gehen"): forms appear.
- [ ] Course: add a chapter, add a resource, mark one done; it shows as done.

**Review**
- [ ] Review: a session shows the cards; answer a few; the result screen appears.
- [ ] For a word with an umlaut or ß (add "Mädchen" or "Straße" first), type it without ("Madchen", "Strasse"). It is marked wrong, with a tip about ä, ö, ü and ß. Typed correctly it is right.
- [ ] **Offline:** switch on airplane mode, review some cards, switch it off. The answers upload (no duplicates, no lost answers).
- [ ] With airplane mode on and the app freshly opened, Review shows a clear message, not a spinner for ever.

**Mistakes and grammar**
- [ ] Log a mistake; it appears in the log with a retry card in Review.
- [ ] Grammar: open a pattern; link it to a chapter.

**Write (needs the AI keys)**
- [ ] Write: type "Ich habe ein Tisch gekauft." It gives a confirmed correction with an explanation. Accept it; it appears in the mistake log.
- [ ] Use up the allowance (or ask): a clear "no checks left" message appears, and everything else still works.

**Today and tests**
- [ ] Add a test with a date and some chapters: a countdown and a readiness message appear.
- [ ] Today shows a plan where every item says why it is there.
- [ ] Account → daily reminder: pick a time, allow notifications. It arrives (a few minutes late is normal).

**Class tasks**
- [ ] In WhatsApp, copy a class message; Class tasks → Add from a WhatsApp message → paste → **Find tasks**. The tasks and dates are right, or fixable on the review screen.
- [ ] Save with a reminder. It arrives at the time shown. Tick the task off: its reminder is cancelled.
- [ ] If your WhatsApp offers Share for a text message, share it to Lumen A1: the text arrives in the box. (Note whether it shows up in the share list at all.)

**Exercise scanner** (Today → ⋮ menu → Scan an exercise from a book)
- [ ] **Take a photo** of a printed exercise (Netzwerk neu). Android asks to allow the camera: allow it. Crop to the one exercise. The text appears for you to check: note what it got wrong (gaps, umlauts, numbers, small print).
- [ ] **This is the first test of the clean-up on real photos**, so please look closely at three or four exercises: are the gaps shown as `___`? Is `ß` right (not a `B`)? Does `Ich` start with a capital I? Is a word that was split over two lines in the book joined up? And, just as important: did the clean-up change anything that was right in the book? Write down each case, with the line as printed and the line as shown.
- [ ] Take a deliberately bad photo (far away, at an angle, in poor light). A warning should say that a lot of the text looks misread and to take the photo again. Note if a good photo ever gets this warning.
- [ ] **Get hints and answers**: a hint per item first, the answer only on tap, each answer labelled. Try an item yourself: write the sentence, check it, accept a correction into the mistake log.
- [ ] An exercise with a picture or audio: the app says what it left out instead of guessing.
- [ ] Choose a photo from the gallery works too. Reading a photo should work without internet once the text-reading model has been downloaded by Google Play services (the first photo may need the internet for that); the hints always need the internet.

**Allango in the app**
- [ ] Add an Allango **audio** link to a chapter (Add resource, kind Audio) and tap **Play**. It loads inside the app. Note: any error or "access denied", whether it asks you to sign in, and whether the sign-in is still there after closing the app.
- [ ] The audio plays. Turn the screen off and switch to another app: note whether it keeps playing.
- [ ] Tick the resource **done** and write a short answer under the player.
- [ ] Do the same with a **video** link, and with a link that won't load: the app should say what happened and **Open in browser** should work.

**Typing** (the keyboard was only ever checked in code, never on a phone)
- [ ] On every screen where you type, the field you are typing in stays visible above the keyboard, and you can scroll to the button below it without closing the keyboard. Try at least: Add word (the lower fields), Log a mistake, Write, Add a result, the scanner's text box, a review card, the answer box under an Allango player, and the search box on the Words tab (scroll to the last word with the keyboard open). On the forms outside the tab bar, scroll to the bottom with the keyboard closed: the last button should sit above the phone's navigation bar, not under it. Note any screen where the keyboard covers the field, or where a large empty gap appears above the keyboard.
- [ ] The long text boxes (Write, the scanner's text, chapter notes) have the same border as the other fields.
- [ ] Optional, if you use TalkBack: a field is announced with its label ("German, edit box"), what you typed is read back, and an error message is spoken when it appears.

**Community chat** (needs two phones, or a phone and a second account; written for 30 people but you only need two to see it work. Never seen on a phone)
- [ ] Today → Community → Open the community chat. With no name yet, the name form appears under the (empty or full) list. A name someone already uses is refused with a message; a free name is accepted.
- [ ] Two phones: a message sent on one appears on the other within a second or two, without reopening the screen. "N here now" shows 2.
- [ ] **Keyboard:** tap the input. The input stays visible just above the keyboard, with no empty gap between them, and the newest message stays visible above the input. Send three messages in a row: the keyboard stays open. Close the keyboard: the input is not under the phone's navigation bar. Type a long text: the input grows to about five lines, then scrolls. Note that on Android the input jumps up once the keyboard has finished opening instead of sliding: that is how this component works, not a fault.
- [ ] Hold a message → Reply: a "Replying to …" strip appears above the input and the sent message quotes the original. ✕ cancels.
- [ ] Hold your own message → Delete: both phones show "Message deleted". Another person's message offers no Delete (unless your email is in `COMMUNITY_MODERATOR_EMAILS`, in which case it does).
- [ ] **Airplane mode:** switch it on, send a message: it shows dimmed, then "Not sent. Tap to try again". Switch it off: the banner "No connection" goes, tap the message → Try again: it is sent once (check the other phone shows it once).
- [ ] While you scroll up to read older messages, a message from the other phone does not move what you are reading and a "New messages" button appears; tapping it goes to the newest. Scrolling to the top loads older messages.
- [ ] Leave the app for an hour (home button), come back: the chat catches up on what was said, nothing missing, nothing twice.
- [ ] Render's free server: after 15 quiet minutes, open the chat. It may take up to a minute to load the first time (the screen says it is still working). Does an open chat keep the server awake? Note what you see.

**Leaving**
- [ ] Sign out, sign in again: your data is all there; the reminder needs setting again.
- [ ] Settings → Apps → Lumen A1 → Permissions: Notifications and Camera, and nothing for microphone, location, contacts.

## Part 2: the two-week trial

**What counts as a blocking issue** (this is a proposal: change it if it doesn't fit you):

A problem that stops you studying that day, or that loses or corrupts your data. For example: you can't sign in; the app crashes on opening or in a normal screen; a review session won't load for more than a few minutes when the server is awake; answers you gave are missing afterwards; a correction was added to your mistake log that you didn't accept; a reminder you set never arrives; the readiness or plan numbers are plainly wrong.

**Not blocking** (note them, but they don't restart the count): the first request after a quiet day takes up to a minute; "AI help isn't available" or "no checks left today" (by design); a screen looks plain; something you'd like but the app never promised (listening practice, screenshots).

**The rule:** 14 days in a row of daily use with no blocking issue. When one happens, it is fixed and the count restarts from 0. You decide when v1 is done.

**Each day, one line.** Copy this table into a note and fill it in:

| Day | Date | Studied? | Blocking issue? (what) | Other notes |
|---|---|---|---|---|
| 1 | | | | |
| … | | | | |
| 14 | | | | |

Also look at these at the end of week one and week two:

- [ ] GitHub → Actions → Database backup: green every night, and its log says `OK: at migration …`.
- [ ] Render: the server's logs show no repeated errors; Sentry (if set up) shows no new errors.
- [ ] The AI allowance: did you ever run out? Was it enough for how you actually study?
- [ ] Did reminders arrive when expected on most days?
