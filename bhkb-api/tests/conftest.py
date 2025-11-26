import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app"
if str(APP_PATH) not in sys.path:
    sys.path.insert(0, str(APP_PATH))

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:devpassword@localhost:5432/postgres")
