# Database Setup Issues and Solutions

| Issue | Analysis | Solution |
|-------|----------|----------|
| `Attribute name 'metadata' is reserved when using the Declarative API` error in audit_log.py | SQLAlchemy reserves the `metadata` attribute for its internal MetaData object. Using it as a column name conflicts with the ORM's declarative API. | Renamed the `metadata` column to `extra_data` in the `AuditLog` model and updated all references in `event_builder.py`. |
| `could not translate host name "db" to address` error when running Alembic | The application configuration was set to connect to a Docker service named "db", but when running outside Docker, it needs to connect to localhost. The database container exposes port 5433 on the host. | Updated `DATABASE_URL` in `.env` and `sqlalchemy.url` in `alembic.ini` from `db:5432` to `localhost:5433` to connect to the Docker container from the host machine. |
| Template rendering failed when creating migrations with `--autogenerate` | The Alembic migration template had undefined variables, likely due to configuration issues or model import problems. | Created the initial migration manually by writing the SQLAlchemy operations directly in a new migration file `25e3615898c8_initial_migration.py` with all table creation statements. |

## Summary

These issues were resolved by:
1. Fixing the reserved column name conflict
2. Configuring proper database connectivity for Docker-based development
3. Manually creating the initial database migration

The database is now properly set up and the application can connect successfully.