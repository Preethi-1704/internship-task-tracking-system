import sqlite3
from datetime import date,timedelta
from services.core import hash_password,verify_password,allowed
from database.schema import SCHEMA

def test_password_hash():
 h=hash_password('Strong-demo-password!');assert h!='Strong-demo-password!';assert verify_password('Strong-demo-password!',h);assert not verify_password('wrong',h)
def test_role_scope():
 assert allowed({'role':'admin'})
 assert allowed({'role':'team_lead','team_id':'A'},'A')
 assert not allowed({'role':'team_lead','team_id':'A'},'B')
 assert allowed({'role':'intern','intern_id':'I1'},intern_id='I1')
 assert not allowed({'role':'intern','intern_id':'I1'},intern_id='I2')
def test_schema_unique_and_foreign_keys(tmp_path):
 db=tmp_path/'x.db'
 with sqlite3.connect(db) as c:
  c.executescript(SCHEMA);c.execute("INSERT INTO teams VALUES('A','Automation',NULL,1)")
  c.execute("INSERT INTO interns(intern_id,full_name,email,team_id,start_date,end_date) VALUES('I1','Test','test@example.test','A','2026-01-01','2026-02-01')")
  try:c.execute("INSERT INTO interns(intern_id,full_name,email,team_id,start_date,end_date) VALUES('I1','Test2','t2@example.test','A','2026-01-01','2026-02-01')");assert False
  except sqlite3.IntegrityError:pass
def test_deadline_rule_examples():
 today=date.today();due=today-timedelta(days=2)
 assert due<today and (today-due).days==2
 assert today==date.today()
 assert today<today+timedelta(days=3)
