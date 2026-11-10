import os
import sys
import tempfile

SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(os.path.dirname(SERVICE_DIR))

# Mirror the image layout: `app` from the service folder, `shared` from the repo root.
sys.path.insert(0, SERVICE_DIR)
sys.path.insert(0, REPO_ROOT)

# shared.database connects at import time, so point it at SQLite before anything imports it.
_db_dir = tempfile.mkdtemp(prefix="deployment-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_db_dir, 'deployment.db')}?check_same_thread=false"
os.environ["ROLLOUT_CONTROLLER_ENABLED"] = "false"
os.environ["ROUTING_TTL_S"] = "0"
