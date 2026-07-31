import sys
import os
from pathlib import Path

# Use /tmp for model caches in serverless environment
os.environ["HF_HOME"] = "/tmp"
os.environ["FASTEMBED_CACHE_PATH"] = "/tmp"

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

for p in [str(BACKEND_DIR), str(ROOT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import importlib.util

main_file = BACKEND_DIR / "api" / "main.py"
spec = importlib.util.spec_from_file_location("backend_main_app", main_file)
main_module = importlib.util.module_from_spec(spec)
sys.modules["backend_main_app"] = main_module
spec.loader.exec_module(main_module)

app = main_module.app

