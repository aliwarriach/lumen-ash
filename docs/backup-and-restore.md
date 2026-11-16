# Backup and restore

The free Supabase plan has no backups, so this project makes its own.

## What happens every night

[.github/workflows/backup.yml](../.github/workflows/backup.yml) runs at 01:30 UTC and:

1. **Dumps** the whole database (our tables, including the dictionary) with `pg_dump`.
2. **Restores** the dump into a throwaway Postgres.
3. **Verifies** the restored copy with [backend/app/restore_check.py](../backend/app/restore_check.py):
   - it is at the migration version the code expects, so the app would start on it;
   - every table and column the app reads is there;
   - row-level security is on for every table;
   - no table came back with fewer rows than the live database had.
4. **Keeps** the dump for 30 days as a GitHub artifact (even if step 3 failed).

If any step fails the job turns red and GitHub emails you. A green run with the lines `OK: at migration …, N tables restored.` in its log means last night's backup is one you could restore from.

**Set it up once:** add the repository secret `SUPABASE_DB_URL` (the session-pooler string, starting `postgresql://`), keep the repository **private** (the dump is all of the learner's study data), then run it by hand once: GitHub → Actions → Database backup → Run workflow. Read the log.

## Restoring for real

Use this if the database was damaged or the Supabase project is gone. You need Docker (or a Postgres 17 client) and `uv`.

1. **Get the dump.** GitHub → Actions → the latest green *Database backup* run → download the `db-backup` artifact → unzip it to get `backup-YYYY-MM-DD.dump`.
2. **Have an empty target database.** Same project, or a new one: create a Supabase project (sign-ups off, as in the README) and copy its *session pooler* connection string. Create the learner's account in Authentication → Users.
3. **Restore.** `--clean` replaces anything in the `public` schema of the target:

   ```sh
   docker run --rm -v "$PWD":/backup postgres:17 \
     pg_restore --clean --if-exists --no-owner --dbname="postgresql://…TARGET…" /backup/backup-YYYY-MM-DD.dump
   ```

   One or two harmless warnings about the `public` schema are normal.
4. **Check it.**

   ```sh
   cd backend
   uv run python -m app.restore_check "postgresql://…TARGET…"
   ```

   It must end with `OK`.
5. **Only if the Supabase project is new: give the data to the new login.** The dump holds our tables but not Supabase's user accounts, and every row is tagged with the learner's user id. A new login has a new id, so without this step the restored data belongs to nobody (the app would look empty).

   ```sh
   # the old id is in the data; the new one is in Supabase → Authentication → Users
   psql "postgresql://…TARGET…" -c "SELECT DISTINCT user_id FROM chapters"
   uv run python -m app.remap_user "postgresql://…TARGET…" OLD_ID NEW_ID
   ```

   It moves everything in one transaction, refuses if the new id already has data, and prints what it moved.

   **Do not open the app with the new login before this step.** A signed-in learner with no chapters is given the starter Allango course the first time the course map loads, which counts as "already has data" and makes this command refuse. If it happens, delete the new login's chapters (`DELETE FROM chapters WHERE user_id = 'NEW_ID'`, which also removes their links) and run it again.
6. **Point the system at the database.**
   - Same Supabase project: nothing to change.
   - New project: in Render set `SUPABASE_URL` and `DATABASE_URL`; the app has the project URL and public key built in, so **build a new APK** (see [INSTALL.md](INSTALL.md)) and install it.
7. Open the app, sign in, and check Today, Review and Words.

## What has and hasn't been tested

Tested, on a local Postgres with data created through the real API: dump with the exact flags the workflow uses → restore into an empty database → `restore_check` passes with the live-database comparison → the API served the words, chapters, mistakes, tasks, tests, reviews and dashboard from the restored copy. `restore_check` was shown to fail on a missing column, a missing table, an old migration version, row-level security switched off and a table that came back empty. `remap_user` is covered by automated tests, including that the old id then sees nothing.

**Not tested** (needs your accounts): the GitHub workflow itself (run it once, as above); a dump from the real Supabase project (it may print extra restore warnings that a local one doesn't, which the verification step is there to judge); restoring into a brand-new Supabase project. Do a full trial restore into a spare free Supabase project once before relying on this.

## Not covered

- The dump is **our tables only** (`--schema=public`). Supabase's own data (the login accounts) isn't in it: if the project is lost, create the learner's account again (step 2) and re-link the data (step 5).
- Backups are nightly, so up to a day of study can be lost. Review answers made offline are kept on the phone until uploaded, which softens this.
- GitHub keeps artifacts 30 days. For a longer history, download one now and then and keep it somewhere private.
