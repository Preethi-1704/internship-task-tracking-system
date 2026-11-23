# User Guide
1. Configure `.env`, set `ADMIN_INITIAL_PASSWORD` to 12+ characters, then launch `streamlit run app.py`.
2. Add teams before interns, then assign tasks.
3. Team leads see their assigned team; interns see their own records.
4. Use Deadline Monitoring for overdue, due-today, upcoming, review-pending and revision lists.
5. Reports & Exports provides CSV and PDF downloads.
6. Use Backup & Settings before maintenance. Restore offline only after checking SQLite integrity.


### Opening the app
The application opens directly to the dashboard without a login screen. Sample records may be initialized when the database is empty. This build is intended for trusted local use; do not expose it to a public/shared network or use confidential real personal data without adding authentication and deployment security.
