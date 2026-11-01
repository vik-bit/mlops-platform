import os
import sys

# Tests run from backend/dataset-service, where `app` is importable as in the image.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
