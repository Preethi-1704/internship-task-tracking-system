import os
from pathlib import Path
from dotenv import load_dotenv

# Project directories
BASE = Path(__file__).resolve().parents[1]

# Load environment variables
load_dotenv(BASE / ".env")

# Database path
DB = Path(
    os.getenv(
        "DATABASE_PATH",
        str(BASE / "dit_internship.db")
    )
)

if not DB.is_absolute():
    DB = BASE / DB

# Company logo
LOGO = BASE / "dit_logo.png"

# Deadline monitoring window
WINDOW = max(
    1,
    int(os.getenv("DEADLINE_WINDOW_DAYS", "3"))
)

# Create required directories
for p in [
    DB.parent,
    BASE / "backups",
    BASE / "logs",
    BASE / "reports" / "generated",
    BASE / "templates",
]:
    p.mkdir(parents=True, exist_ok=True)
