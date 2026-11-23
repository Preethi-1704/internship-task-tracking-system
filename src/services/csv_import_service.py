"""Atomic, validated CSV/XLSX import service for DIT ."""
from datetime import date
from io import BytesIO
from pathlib import Path
import re
import pandas as pd
from database.connection import connect
from services.core import audit

SCHEMAS = {
    'intern_master': ['intern_id','full_name','email','phone','team_id','start_date','end_date'],
    'team_master': ['team_id','team_name','lead_username'],
    'task_register': ['task_id','title','description','intern_id','team_id','assigned_date','due_date','submission_date','status','assessment_status','priority'],
    'attendance': ['intern_id','attendance_date','status','check_in','check_out','remarks'],
}
TASK_STATUSES={'Not Started','In Progress','Submitted','Reviewed'}
ASSESSMENTS={'Pending','Passed','Need Revision','Needs Revision','Fail'}
PRIORITIES={'Low','Medium','High','Critical'}
ATTENDANCE={'Present','Absent','Leave','Holiday'}

def _read(filename, payload):
    ext=Path(filename).suffix.lower()
    if ext=='.csv': return pd.read_csv(BytesIO(payload),dtype=str,keep_default_na=False,encoding='utf-8-sig')
    if ext=='.xlsx': return pd.read_excel(BytesIO(payload),dtype=str,keep_default_na=False)
    raise ValueError('Only CSV and XLSX files are supported.')

def _valid_date(value, field, row, errors, optional=False):
    value=str(value or '').strip()
    if optional and not value: return None
    try: return date.fromisoformat(value).isoformat()
    except (ValueError,TypeError):
        errors.append({'row':row,'field':field,'reason':'Expected date in YYYY-MM-DD format'}); return None

def import_records(filename, payload, actor):
    stem=Path(filename).stem.lower().replace('_template','')
    kind=next((k for k in SCHEMAS if stem==k or stem.replace('_','')==k.replace('_','')),None)
    if not kind:
        return {'kind':None,'read':0,'imported':0,'rejected':0,'duplicates':0,'errors':[{'row':0,'field':'filename','reason':'Filename must identify intern_master, team_master, task_register, or attendance.'}]}
    try: df=_read(filename,payload)
    except Exception as exc:
        return {'kind':kind,'read':0,'imported':0,'rejected':0,'duplicates':0,'errors':[{'row':0,'field':'file','reason':f'Unable to read file ({type(exc).__name__})'}]}
    df.columns=[str(x).strip().lower() for x in df.columns]
    missing=[x for x in SCHEMAS[kind] if x not in df.columns]
    if missing:
        errs=[{'row':1,'field':'columns','reason':'Missing columns: '+', '.join(missing)}]
        return {'kind':kind,'read':len(df),'imported':0,'rejected':len(df),'duplicates':0,'errors':errs}
    df=df[SCHEMAS[kind]].fillna('').astype(str)
    errors=[]; valid=[]; seen=set()
    with connect() as c:
        for rowno, rec0 in enumerate(df.to_dict('records'),start=2):
            r={k:str(v).strip() for k,v in rec0.items()}; e=[]
            def req(field):
                if not r.get(field): e.append({'row':rowno,'field':field,'reason':'Required value is blank'})
            if kind=='intern_master':
                for f in ['intern_id','full_name','email','team_id','start_date','end_date']: req(f)
                r['intern_id']=r['intern_id'].upper()
                key=r['intern_id']
                if key in seen:e.append({'row':rowno,'field':'intern_id','reason':'Duplicate ID within file'})
                seen.add(key)
                if r['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',r['email']):e.append({'row':rowno,'field':'email','reason':'Invalid email format'})
                a=_valid_date(r['start_date'],'start_date',rowno,e); b=_valid_date(r['end_date'],'end_date',rowno,e)
                if a and b and b<a:e.append({'row':rowno,'field':'end_date','reason':'End date precedes start date'})
                if c.execute('SELECT 1 FROM interns WHERE intern_id=?',(key,)).fetchone():e.append({'row':rowno,'field':'intern_id','reason':'ID already exists in database'})
                if not c.execute('SELECT 1 FROM teams WHERE team_id=? AND active=1',(r['team_id'],)).fetchone():e.append({'row':rowno,'field':'team_id','reason':'Team does not exist or is inactive'})
                if r['email'] and c.execute('SELECT 1 FROM interns WHERE email=?',(r['email'].lower(),)).fetchone():e.append({'row':rowno,'field':'email','reason':'Email already exists in database'})
                r.update(email=r['email'].lower(),start_date=a,end_date=b)
            elif kind=='team_master':
                req('team_id');req('team_name');r['team_id']=r['team_id'].upper();key=r['team_id']
                if key in seen:e.append({'row':rowno,'field':'team_id','reason':'Duplicate ID within file'})
                seen.add(key)
                if c.execute('SELECT 1 FROM teams WHERE team_id=?',(key,)).fetchone():e.append({'row':rowno,'field':'team_id','reason':'ID already exists in database'})
                if r['lead_username']:
                    lead=c.execute('SELECT role,active FROM users WHERE username=?',(r['lead_username'],)).fetchone()
                    if not lead or lead['role']!='team_lead' or not lead['active']:e.append({'row':rowno,'field':'lead_username','reason':'Must reference an active team_lead user or be blank'})
            elif kind=='task_register':
                for f in ['task_id','title','intern_id','team_id','assigned_date','due_date','status','assessment_status','priority']:req(f)
                r['task_id']=r['task_id'].upper();key=r['task_id']
                if key in seen:e.append({'row':rowno,'field':'task_id','reason':'Duplicate ID within file'})
                seen.add(key)
                if c.execute('SELECT 1 FROM tasks WHERE task_id=?',(key,)).fetchone():e.append({'row':rowno,'field':'task_id','reason':'ID already exists in database'})
                a=_valid_date(r['assigned_date'],'assigned_date',rowno,e); d=_valid_date(r['due_date'],'due_date',rowno,e); s=_valid_date(r['submission_date'],'submission_date',rowno,e,True)
                if a and d and d<a:e.append({'row':rowno,'field':'due_date','reason':'Due date precedes assignment date'})
                if a and s and s<a:e.append({'row':rowno,'field':'submission_date','reason':'Submission precedes assignment date'})
                if r['status'] not in TASK_STATUSES:e.append({'row':rowno,'field':'status','reason':'Unsupported task status'})
                if r['assessment_status'] not in ASSESSMENTS:e.append({'row':rowno,'field':'assessment_status','reason':'Unsupported assessment status'})
                if r['priority'] not in PRIORITIES:e.append({'row':rowno,'field':'priority','reason':'Unsupported priority'})
                i=c.execute('SELECT team_id,active FROM interns WHERE intern_id=?',(r['intern_id'],)).fetchone()
                if not i or not i['active']:e.append({'row':rowno,'field':'intern_id','reason':'Intern does not exist or is inactive'})
                elif i['team_id']!=r['team_id']:e.append({'row':rowno,'field':'team_id','reason':"Team must match intern's current team"})
                if r['status'] in {'Submitted','Reviewed'} and not s:e.append({'row':rowno,'field':'submission_date','reason':'Submitted or Reviewed tasks require a submission date'})
                if r['status']=='Reviewed' and r['assessment_status']=='Pending':e.append({'row':rowno,'field':'assessment_status','reason':'Reviewed task needs Passed, Need Revision, or Fail'})
                if r['assessment_status']=='Passed' and r['status']!='Reviewed':e.append({'row':rowno,'field':'status','reason':'Passed tasks must have Reviewed status'})
                r.update(assigned_date=a,due_date=d,submission_date=s or None)
            else:
                for f in ['intern_id','attendance_date','status']:req(f)
                d=_valid_date(r['attendance_date'],'attendance_date',rowno,e)
                if r['status'] not in ATTENDANCE:e.append({'row':rowno,'field':'status','reason':'Use Present, Absent, Leave, or Holiday'})
                if not c.execute('SELECT 1 FROM interns WHERE intern_id=? AND active=1',(r['intern_id'],)).fetchone():e.append({'row':rowno,'field':'intern_id','reason':'Intern does not exist or is inactive'})
                key=(r['intern_id'],d)
                if key in seen:e.append({'row':rowno,'field':'intern_id/attendance_date','reason':'Duplicate attendance entry within file'})
                seen.add(key)
                if d and c.execute('SELECT 1 FROM attendance WHERE intern_id=? AND attendance_date=?',(r['intern_id'],d)).fetchone():e.append({'row':rowno,'field':'attendance_date','reason':'Attendance already exists in database'})
                if r['check_in'] and r['check_out'] and r['check_out']<r['check_in']:e.append({'row':rowno,'field':'check_out','reason':'Check-out time precedes check-in'})
                r['attendance_date']=d
            if e: errors.extend(e)
            else: valid.append(r)
    result={'kind':kind,'read':len(df),'imported':0,'rejected':len(df) if errors else 0,'duplicates':sum(('Duplicate' in x['reason'] or 'already exists' in x['reason']) for x in errors),'errors':errors}
    if errors:
        audit(actor,'csv_import',kind,filename,'failure',f'{len(errors)} validation errors; atomic import cancelled')
        return result
    try:
        with connect() as c:
            for r in valid:
                if kind=='intern_master':
                    c.execute('INSERT INTO interns(intern_id,full_name,email,phone,team_id,start_date,end_date) VALUES(?,?,?,?,?,?,?)',(r['intern_id'],r['full_name'],r['email'],r['phone'],r['team_id'],r['start_date'],r['end_date']))
                elif kind=='team_master':
                    c.execute('INSERT INTO teams(team_id,team_name,lead_username,active) VALUES(?,?,?,1)',(r['team_id'],r['team_name'],r['lead_username'] or None))
                    if r['lead_username']: c.execute("UPDATE users SET team_id=? WHERE username=? AND role='team_lead'",(r['team_id'],r['lead_username']))
                elif kind=='task_register':
                    c.execute('INSERT INTO tasks(task_id,title,description,intern_id,team_id,assigned_date,due_date,submission_date,status,assessment_status,priority,assigned_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(r['task_id'],r['title'],r['description'],r['intern_id'],r['team_id'],r['assigned_date'],r['due_date'],r['submission_date'],r['status'],r['assessment_status'],r['priority'],actor))
                    if r['status']=='Reviewed':c.execute('INSERT INTO reviews(task_id,reviewer,assessment_status,comments) VALUES(?,?,?,?)',(r['task_id'],actor,r['assessment_status'],'Imported via validated template'))
                else:
                    c.execute('INSERT INTO attendance(intern_id,attendance_date,status,check_in,check_out,remarks,recorded_by) VALUES(?,?,?,?,?,?,?)',(r['intern_id'],r['attendance_date'],r['status'],r['check_in'] or None,r['check_out'] or None,r['remarks'],actor))
        result['imported']=len(valid);result['rejected']=0
        audit(actor,'csv_import',kind,filename,'success',f'Imported {len(valid)} rows atomically')
    except Exception as exc:
        result['imported']=0;result['rejected']=len(df);result['errors']=[{'row':0,'field':'database','reason':f'Transaction rolled back ({type(exc).__name__})'}]
        audit(actor,'csv_import',kind,filename,'failure','Database transaction rolled back')
    return result
