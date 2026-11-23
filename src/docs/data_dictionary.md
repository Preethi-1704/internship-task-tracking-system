# Data Dictionary
- users: username, password_hash, role, intern_id, team_id, active.
- teams: team_id, team_name, lead_username, active.
- interns: intern_id, full_name, email, team_id, start_date, end_date, active.
- tasks: task_id, intern_id, team_id, assigned_date, due_date, submission_date, status, assessment_status, priority.
- attendance: intern_id, attendance_date, status, times, remarks; unique intern/date.
- reviews: task, reviewer, assessment, comments, timestamp.
- notifications: recipient, task, kind, channel, delivery status/reason.
- audit_logs: actor, operation, entity, outcome, timestamp.
