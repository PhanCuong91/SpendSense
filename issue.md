# Database Setup Issues and Solutions

| Issue | Analysis | Solution |
|-------|----------|----------|
| `Attribute name 'metadata' is reserved when using the Declarative API` error in audit_log.py | SQLAlchemy reserves the `metadata` attribute for its internal MetaData object. Using it as a column name conflicts with the ORM's declarative API. | Renamed the `metadata` column to `extra_data` in the `AuditLog` model and updated all references in `event_builder.py`. |
| `could not translate host name "db" to address` error when running Alembic | The application configuration was set to connect to a Docker service named "db", but when running outside Docker, it needs to connect to localhost. The database container exposes port 5433 on the host. | Updated `DATABASE_URL` in `.env` and `sqlalchemy.url` in `alembic.ini` from `db:5432` to `localhost:5433` to connect to the Docker container from the host machine. |
| Template rendering failed when creating migrations with `--autogenerate` | The Alembic migration template had undefined variables, likely due to configuration issues or model import problems. | Created the initial migration manually by writing the SQLAlchemy operations directly in a new migration file `25e3615898c8_initial_migration.py` with all table creation statements. |
| Module path error: `Error while finding module specification for 'app.worker.poller_worker'` | The worker modules were located in `app/workers/` directory (plural), but the README and import statements referenced `app.worker` (singular). | Updated all references in README.md from `app.worker.*` to `app.workers.*` to match the actual directory structure. |
| Missing dependency: `ModuleNotFoundError: No module named 'dateutil'` | The parsing module imports `dateutil` library which was not listed in `requirements.txt`. | Added `python-dateutil` to `requirements.txt` and installed it with `pip install python-dateutil`. |
| Circular import: `NameError: name 'CorrelationLink' is not defined` | `ParsedTransactionCandidate` model defined relationships to `CorrelationLink` but didn't import it, causing the relationship initialization to fail when SQLAlchemy tried to resolve the string reference. Additionally, two foreign keys between the same tables caused ambiguous join conditions. | Created `app/db/models/__init__.py` to import all models in the correct order, updated `ParsedTransactionCandidate` to import `CorrelationLink` directly, and used explicit column references in `foreign_keys` parameter: `foreign_keys=[CorrelationLink.debit_candidate_id]`. Updated `gmail/poller.py` to import models from the package. |
| Database schema mismatch: `(psycopg2.errors.UndefinedColumn) column "error_type" of relation "error_log" does not exist` | The migration file had incorrect column names (`error_message`, `stack_trace`, `timestamp`) that didn't match the `ErrorLog` model which expected `error_type`, `stack`, and `created_at`. | Updated the migration file `25e3615898c8_initial_migration.py` to use the correct column names and types that match the `ErrorLog` model definition. Dropped and recreated the database with the corrected migration. |
| Foreign key violation: `insert or update on table "error_log" violates foreign key constraint "error_log_email_id_fkey"` | The `ErrorLog` was being created with `email_id` set to the `ParsedTransactionCandidate.id` instead of the actual `email_id` from the candidate. This caused foreign key violations when the candidate ID didn't exist in the `email_raw` table. | Updated `EventBuilder._log_error()` to accept `email_id` parameter and pass `candidate.email_id` instead of `candidate_id`. |
| Database schema mismatch: `(psycopg2.errors.UndefinedColumn) column "event_type" of relation "event" does not exist` | The migration file had incorrect column names and structure for the `event` table (`type` instead of `event_type`, nullable fields that should be required, single `email_id` instead of `raw_email_ids` JSON array). | Updated the migration file `25e3615898c8_initial_migration.py` to match the `Event` model: `event_type` (required), `sender`/`receiver` (required), `amount` (required), `currency` (required with default), `datetime_sgt` (required), `raw_email_ids` (JSON required), `description` (optional). Dropped and recreated the event table. |
| AttributeError: `'NoneType' object has no attribute 'lower'` in classifier | The `classify()` function attempted to call `.lower()` on `inferred_sender` and `inferred_receiver` without checking if they were `None`, causing crashes when email parsing failed to extract sender/receiver information. | Added null checks in the rule matching logic: `if inferred_sender and inferred_receiver and rule["sender"].lower() == inferred_sender.lower() and rule["receiver"].lower() == inferred_receiver.lower()` to prevent calling `.lower()` on `None` values. |
| EventBuilder NotNullViolation Issue | The `event` table requires `sender` and `receiver` fields to be non-null. The parser or classifier sometimes fails to extract these fields, resulting in `None` values. Attempting to create an Event with missing sender/receiver violates the database constraint and causes a transaction rollback. The log shows that EventBuilder attempted to create events with missing sender/receiver multiple times. | Add validation in `EventBuilder.process_candidate()` to check if `sender` or `receiver` is `None` before creating an Event. If either is missing, log an error and skip event creation. This prevents database constraint violations and ensures only valid events are created. |

## Summary

All issues were resolved through the following steps:
1. **Reserved column naming**: Renamed `metadata` to `extra_data` in `AuditLog` model
2. **Database connectivity**: Changed connection string from Docker service "db" to "localhost:5433"
3. **Manual migration**: Created migration file manually after autogenerate failed
4. **Module paths**: Corrected module paths from singular `worker` to plural `workers`
5. **Missing dependencies**: Added `python-dateutil` to requirements and installed it
6. **Circular imports**: Fixed import order by creating `app/db/models/__init__.py` and updating relationship definitions with explicit foreign key column references
7. **Schema mismatch**: Updated ErrorLog migration columns from `error_message`/`stack_trace`/`timestamp` to match model: `error_type`/`stack`/`created_at`
8. **Foreign key violation**: Fixed ErrorLog to use `candidate.email_id` instead of `candidate.id` for foreign key reference
9. **Event table schema**: Corrected event table migration to match Event model with proper column names and constraints
10. **Classification crash**: Added null checks in classifier to prevent calling `.lower()` on None values
11. **EventBuilder NotNullViolation**: Added validation in `process_candidate()` to check for missing sender/receiver

## Current Status

✅ **FastAPI server**: Running on port 8000  
✅ **Database**: Connected, migrated with correct schema  
✅ **Workers**: Can be started without import errors  
✅ **ORM models**: All models properly initialized with correct relationships  
✅ **No circular import issues**: Models load in proper dependency order
✅ **Error logging**: ErrorLog table has correct columns and can store errors with valid foreign keys  
✅ **Worker processes**: Parser and poller workers can run and write to database
✅ **Event creation**: Events are successfully created from parsed email candidates
✅ **Classification**: Handles missing sender/receiver data gracefully without crashes


