import os
from pathlib import Path
from dotenv import load_dotenv
BASE=Path(__file__).resolve().parents[1]
load_dotenv(BASE/'.env')
DB=Path(os.getenv('DATABASE_PATH',str(BASE/'data'/'dit_internship.db')))
if not DB.is_absolute(): DB=BASE/DB
LOGO=BASE/'assets'/'dit_logo.png'
WINDOW=max(1,int(os.getenv('DEADLINE_WINDOW_DAYS','3')))
for p in [DB.parent,BASE/'backups',BASE/'logs',BASE/'reports'/'generated',BASE/'templates']: p.mkdir(parents=True,exist_ok=True)
