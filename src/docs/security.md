# Security Notes
PBKDF2-HMAC-SHA256 password hashing with per-password random salt; parameterized SQL; backend data scoping; `.env` ignored by git. Restrict file permissions for SQLite and backups. Use HTTPS and a hardened deployment before exposing the app. Demo credentials must be changed. SQLite itself has no row-level user access control; authorization is application-level.
