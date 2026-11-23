from pathlib import Path
import sqlite3
import database.connection as dbconn
from database.schema import SCHEMA
from services.csv_import_service import import_records


def setup_db(tmp_path, monkeypatch):
    path = tmp_path / 'test.db'
    monkeypatch.setattr(dbconn, 'DB', path)
    with sqlite3.connect(path) as c:
        c.executescript(SCHEMA)
        c.execute("INSERT INTO teams(team_id,team_name,active) VALUES('TEAM-A','Automation',1)")
    return path


def test_csv_import_saves_valid_intern_atomically(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    payload = b'intern_id,full_name,email,phone,team_id,start_date,end_date\nDIT-X001,Test User,test@example.test,123,TEAM-A,2026-01-01,2026-03-01\n'
    result = import_records('intern_master_template.csv', payload, 'admin')
    assert result['imported'] == 1
    assert result['errors'] == []
    with dbconn.connect() as c:
        assert c.execute("SELECT full_name FROM interns WHERE intern_id='DIT-X001'").fetchone()[0] == 'Test User'


def test_csv_import_rejects_entire_file_when_any_row_invalid(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    payload = (b'intern_id,full_name,email,phone,team_id,start_date,end_date\n'
               b'DIT-X001,Good User,good@example.test,123,TEAM-A,2026-01-01,2026-03-01\n'
               b'DIT-X002,Bad User,not-an-email,123,NO-TEAM,2026-03-01,2026-01-01\n')
    result = import_records('intern_master_template.csv', payload, 'admin')
    assert result['imported'] == 0
    assert result['rejected'] == 2
    assert result['errors']
    with dbconn.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM interns').fetchone()[0] == 0
