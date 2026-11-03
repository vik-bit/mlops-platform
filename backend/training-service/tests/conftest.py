import os
import sys

# Tests run from backend/training-service, where `app` is importable as in the image; `shared`
# sits at the repo root (the image copies it to /app/shared).
SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(os.path.dirname(SERVICE_DIR))
sys.path.insert(0, SERVICE_DIR)
sys.path.insert(0, REPO_ROOT)
