import os
import sys
import tempfile

# Tests run from backend/training-service, where `app` is importable as in the image; `shared`
# sits at the repo root (the image copies it to /app/shared).
SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(os.path.dirname(SERVICE_DIR))
sys.path.insert(0, SERVICE_DIR)
sys.path.insert(0, REPO_ROOT)

# shared.database connects at import time (app.services.retrain imports it): use SQLite in tests.
_db_dir = tempfile.mkdtemp(prefix="training-tests-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(_db_dir, 'training.db')}?check_same_thread=false")
