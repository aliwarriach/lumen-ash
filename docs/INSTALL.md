# Build and install the app

The app is an Android APK installed directly (no Play Store). This guide has two parts: building it (for whoever maintains it) and installing it (for the learner).

## Build a signed release APK

A release build uses the **production** profile in [app/eas.json](../app/eas.json). It is built by Expo's free build service (EAS). It queues and has a monthly limit on the free plan; building on your own Mac needs Android tooling (`eas build --local`) and is not covered here.

1. **Once:** create a free Expo account, then `cd app && npx eas-cli@latest login` and `npx eas-cli@latest init`.
2. **Once: give the build its settings.** These three values are public (they are inside the APK anyway), but `app/.env` is not uploaded to EAS, so set them there:

   ```sh
   cd app
   npx eas-cli@latest env:create --environment production --name EXPO_PUBLIC_SUPABASE_URL --value https://YOUR-PROJECT.supabase.co --visibility plaintext
   npx eas-cli@latest env:create --environment production --name EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY --value YOUR-PUBLISHABLE-KEY --visibility plaintext
   npx eas-cli@latest env:create --environment production --name EXPO_PUBLIC_API_URL --value https://YOUR-SERVICE.onrender.com --visibility plaintext
   ```

   The API URL must be **https** (Android blocks plain http in release builds). Never use the Supabase *secret* key, and never put the Gemini or Groq keys here.
3. **Build:** `npx eas-cli@latest build -p android --profile production`. The first time it asks to generate an Android keystore: say yes. This is the app's **signing key**.
4. **Back up the signing key now:** `npx eas-cli@latest credentials -p android`, choose the production build, download the keystore and its passwords, and keep them somewhere private and safe (a password manager, not this repository). If you lose it you can't ship updates that install over the old app: the learner would have to uninstall (losing any answers not yet uploaded) and install fresh.
5. When the build finishes, EAS shows a link to the `.apk`. Download it, or send the link to the learner.

The version number goes up by itself on every production build (`autoIncrement`). Change `version` in `app/app.json` only for a release you want to name.

**What the release build changes** compared with a development build: it asks Android for fewer permissions (it removes "draw over other apps" and shared-storage access, see [app/app.config.js](../app/app.config.js)), and Android's cloud backup of the app's data is off (`allowBackup: false`), so the saved sign-in is never copied to a Google account. To check the finished APK's permissions: `aapt dump permissions app.apk` (from Android build tools). Expected: internet, notifications, vibrate, audio settings, and the notification-related ones Expo adds, and **camera** (added in Phase 11 so you can photograph an exercise; the photo is read on the phone and deleted). There must be nothing for microphone, location or contacts.

## Install on the phone

1. Open the APK link on the phone (or copy the file over) and tap it.
2. Android asks to allow installing from this source (Chrome, Files or whichever app you opened it from). Allow it, then tap **Install**. Later you can switch that permission off again.
3. Open **Lumen A1** and sign in with the account that was created for you.
4. When asked, **allow notifications**: they are how reminders reach you.
5. **Daily reminder:** Today → Account and daily reminder → pick a time.

To **update**, install the new APK over the old one: your data lives on the server, so nothing is lost. (If Android says the app can't be installed over the old one, the signing key changed: see step 4 above.)

## Sharing from WhatsApp

Press and hold a class message in WhatsApp and tap Copy, then Today → Class tasks → Add from a WhatsApp message and paste. If your WhatsApp offers **Share** for the message, choose **Lumen A1** from the list and the text arrives ready to use.

## When something doesn't work

| What you see | What it means | What to do |
|---|---|---|
| The app opens on "This copy of the app isn't set up" | The APK was built without one of its three settings, or with a wrong one. The screen names it. | Whoever builds the app: set the value in EAS (step 2 above) and build again. Nothing on the phone can fix it. |
| "Can't reach the server…" | No internet, or the server is asleep | Wait a minute and try again. The free server sleeps when unused and wakes in up to a minute. Reviews you answered are kept on the phone and upload later. |
| A spinner for a long time, then "taking too long" | The server is waking up | Try again in a minute. |
| Account says **Server: Unreachable** even after waiting a few minutes | The database project may be paused, or the server is down | Supabase pauses free projects after about a week of no use: open its dashboard and press **Restore project**. If it isn't paused, check the Render dashboard. |
| "AI help isn't available right now" | The free AI allowance is used up, or the AI service is down | Everything else still works. Try again later. If it never comes back, the AI model may have been retired: see "AI" in the README. |
| "A lot of this looks misread…" after a photo | The phone could not read the photo well | Take it again: closer, in good light, page flat, no shadow. Or correct the text by hand, or type the exercise. |
| Reminders don't arrive | Notifications blocked, or battery saving | Android settings → Apps → Lumen A1 → Notifications on; Battery → unrestricted. |
| "Your sign-in has expired" | The saved login is no longer valid | Sign out (Account) and sign in again. |
