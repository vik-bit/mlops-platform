import os
import sys
import tempfile

SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(os.path.dirname(SERVICE_DIR))

# Mirror the image layout: `app` from the service folder, `shared` from the repo root.
sys.path.insert(0, SERVICE_DIR)
sys.path.insert(0, REPO_ROOT)

# shared.database connects at import time, and jwt_handler reads its key at import
# time, so both must be configured before any test module imports the app.
_db_dir = tempfile.mkdtemp(prefix="gateway-tests-")
os.environ["DATABASE_URL"] = (
    f"sqlite:///{os.path.join(_db_dir, 'gateway.db')}?check_same_thread=false"
)
os.environ["JWT_SECRET_KEY"] = "test-signing-key"
os.environ.pop("ADMIN_PASSWORD", None)
