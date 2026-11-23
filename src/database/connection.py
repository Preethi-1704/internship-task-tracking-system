import sqlite3
from config.settings import DB
from database.schema import SCHEMA
def connect():
 c=sqlite3.connect(DB,timeout=15); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
def init_db():
 with connect() as c: c.executescript(SCHEMA)
