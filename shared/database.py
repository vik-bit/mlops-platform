import os
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


# Render injects this via render.yaml's fromDatabase: connectionString.
# Locally (docker-compose), it falls back to the old hardcoded value so
# nothing breaks in dev. Never hardcode this as the only option — Render
# has no service literally named "postgres" in its DNS.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://admin:admin@postgres:5432/mlops_platform",
)

# Name the driver explicitly. SQLAlchemy 2.1 maps a bare postgresql:// URL to psycopg 3, but the
# services install psycopg2-binary, so every fresh image failed to connect. Render may also hand
# out the older postgres:// scheme.
for _scheme in ("postgresql://", "postgres://"):
    if DATABASE_URL.startswith(_scheme):
        DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len(_scheme):]

MAX_RETRIES = 10
RETRY_DELAY = 5

engine = None

for i in range(MAX_RETRIES):
    try:
        engine = create_engine(DATABASE_URL)
        connection = engine.connect()
        connection.close()
        print("Database connected successfully!")
        break
    except Exception as e:
        print(f"Database connection failed: {e}")
        print(f"Retrying in {RETRY_DELAY} seconds...")
        time.sleep(RETRY_DELAY)

if engine is None:
    raise Exception("Could not connect to PostgreSQL.")

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()