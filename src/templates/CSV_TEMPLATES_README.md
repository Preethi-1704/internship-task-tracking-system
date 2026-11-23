# CSV templates and automated import

The folder includes CSV templates for intern master, team master, task register, and attendance. Open them with Excel or a text editor and retain the exact header names. Dates must use ISO format `YYYY-MM-DD`; use UTF-8 encoding.

## Import workflow
1. Download the matching `.csv` or `.xlsx` template from the application's **Excel Import Center**.
2. Fill in the rows and preserve the required column names.
3. Upload the file (maximum 5 MB).
4. Review the preview and select **Validate and Import to Database**.
5. If validation fails, the whole file is rejected and no records are saved. Download `import_validation_errors.csv`, correct the indicated row/field values, and retry.
6. On success, the application reports the number of records committed to SQLite and writes an audit-log entry.

Imports are atomic and do not overwrite existing IDs. Create teams before importing interns, interns before importing tasks, and interns before importing attendance. `team_master` may reference an existing active Team Lead username or leave `lead_username` blank. For task imports, the task's team must match the intern's current team.
