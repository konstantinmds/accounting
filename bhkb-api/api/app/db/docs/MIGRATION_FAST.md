• Yes. After your recent changes the container will auto-run migrations on startup, but you still need to generate
  the migration files when you change the schema—just like makemigrations/migrate in Django. Here’s the full
  workflow and why each piece is there:

### 1. Make your schema change in code

- Update the SQLAlchemy models in api/app/db/models.py, or adjust other DB-layer code.
- We also keep api/app/schema.sql as the canonical schema definition; for major changes, update that too so the
  initial migration stays truthful.

### 2. Generate a migration (the Alembic equivalent of makemigrations)

  cd bhkb-api/api
  alembic revision --autogenerate -m "describe your change"

  Because api/alembic/env.py now sets target_metadata = models.Base.metadata, Alembic will diff the ORM models and
  produce a draft migration in api/alembic/versions/. Review the generated file and edit if needed (sometimes manual
  tweaks are still required).

### 3. Apply the migration locally (equivalent to python manage.py migrate)

  alembic upgrade head

  or from the repo root: make migrate (the Makefile runs the same command). This upgrades your local/Postgres
  instance so tests and the app use the new schema.

### 4. Commit the migration file

  Add the new file under api/alembic/versions/ to git. Without it, other environments (and Docker) can’t reproduce
  your schema change.

### 5. Container startup automatically runs migrations

  When the FastAPI app starts, its lifespan hook calls run_migrations(settings.DATABASE_URL), which runs alembic
  upgrade head. So as long as the migration files are in the image (be sure the Dockerfile includes COPY alembic.ini
  and COPY alembic ./alembic), the database in Docker will stay current. If Alembic isn’t copied, the startup will
  fail—so update the Dockerfile accordingly.

### 6. Optional: downgrade

  If you misfire, make downgrade (or alembic downgrade -1) reverts the last migration.

### How this compares to Django

- Django: makemigrations generates migrations; migrate applies them; the app loads in a project context so you
  rarely “install” it.
- FastAPI + Alembic: same idea, but the commands are alembic revision --autogenerate and alembic upgrade. Because
  we package the app, we run pip install -e api (setuptools makes app.* importable) and migrations happen either
  via CLI or automatically at startup.

  So your everyday checklist for schema updates:
  5. Rebuild/restart containers; they’ll upgrade themselves thanks to the lifespan hook.

  That’s the complete picture end-to-end.
