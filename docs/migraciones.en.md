# Migrations and engine change

This guide describes how to change the database schema and how to move data from SQLite to PostgreSQL (or back). The tests in `backend/tests/migrations/` check both procedures on every change.

## Migration rules

- **One migration per change**, with a descriptive name (`0003_add_watch_interval.py`). A migration already merged into `main` is never edited: a mistake gets a new migration.
- **Schema and data separately.** A data migration (`RunPython`) does not mix in table changes, so each one can be reverted on its own.
- **Always reversible.** Every `RunPython` has a `reverse_code`, and every schema operation must be undoable. The round-trip test checks this for each app.
- **Expand and contract** for destructive changes. First add the new structure and have the code write to both places; then migrate the data; and only in a later migration remove the old one.
- **ORM only.** No `RunSQL` and no hand-written SQL, so the same migration works on SQLite and PostgreSQL.
- **Squash periodically**, once an app's history gets long.

## Commands to inspect and revert

```bash
python manage.py showmigrations                 # state of each migration
python manage.py sqlmigrate catalog 0002        # SQL it would run, without applying it
python manage.py sqlmigrate catalog 0002 --backwards
python manage.py migrate catalog 0001           # revert back to 0001
python manage.py migrate                        # apply everything pending
```

Before a migration is merged, CI checks that `makemigrations --check` finds no unmigrated changes, that `lintmigrations` flags no dangerous operations, and that the round-trip test passes on both engines.

## Moving from SQLite to PostgreSQL

Data moves with `dumpdata` and `loaddata`, never with SQL. Stop the service first.

1. **Export from the current engine** (SQLite, by default):

   ```bash
   python manage.py dumpdata --exclude contenttypes --exclude auth.permission \
       --indent 2 --output data.json
   ```

   Django regenerates content types and permissions, so they are not exported.

2. **Prepare the new database** with the schema applied and empty:

   ```bash
   export DATABASE_URL=postgres://user:password@server:5432/glissandi
   python manage.py migrate
   ```

3. **Load the data**:

   ```bash
   python manage.py loaddata data.json
   ```

4. **Check** that the counts match between the two engines (for example, with `python manage.py shell -c "from catalog.models import Track; print(Track.objects.count())"`).

Run `loaddata` only on an empty database. If rows with the same primary key already exist, they are overwritten, and append-only records (activity, runs, logs) must not be altered.

To move from PostgreSQL back to SQLite, follow the same steps and change `DATABASE_URL`.

## Related tests

- `backend/tests/migrations/test_round_trip.py`: reverts each app to zero, applies it again and checks that no migrations are pending.
- `backend/tests/migrations/test_empty_database.py`: a freshly migrated database holds only the role groups and `/api/health/` responds.
- `backend/tests/migrations/test_dump_load.py`: dumping and loading keeps the data.
