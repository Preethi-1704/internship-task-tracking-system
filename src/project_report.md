# Project Report — 
## Abstract
A Streamlit and SQLite system to centralize internship records, teams, task lifecycle, attendance, assessments, deadline follow-up and reporting.
## Business problem
Spreadsheet-based tracking can create duplicate IDs, missed deadlines and inconsistent reporting. The system applies validation, scope restrictions and database constraints.
## Architecture
Streamlit UI → service functions → SQLite schema; Pandas/OpenPyXL handle workbook templates and exports; Plotly charts dashboard data; ReportLab creates PDF output.
## Workflow
```mermaid
flowchart TD
A[Start]-->B[Authentication]-->C{Valid?}
C--No-->D[Audit failed login]-->B
C--Yes-->E[Role validation]-->F[Dashboard]-->G[Select module]-->H{Input valid?}
H--No-->I[Show validation error]-->G
H--Yes-->J[Save transaction]-->K[Audit event]-->L[Refresh dashboard]-->M[Report or follow-up]-->N[End]
```
## Excel import
```mermaid
flowchart TD
A[Upload XLSX]-->B{Type and size valid?}
B--No-->X[Reject]
B--Yes-->C[Read workbook]-->D{Required columns valid?}
D--No-->X
D--Yes-->E[Preview with source rows]-->F[Manual correction]
F-->G[Import disabled in this release]
```
## Submission and assessment
```mermaid
flowchart TD
A[Intern progresses task]-->B[Submit]-->C[Reviewer queue]-->D{Outcome}
D--Passed-->E[Reviewed / Passed]-->F[Completion metric]
D--Needs Revision-->G[Revision follow-up]-->A
```
## Deadline monitoring
```mermaid
flowchart TD
A[Read task]-->B{Past due and unsubmitted?}
B--Yes-->C[Overdue + days overdue]
B--No-->D{Due today?}
D--Yes-->E[Due today]
D--No-->F{Within next 3 days?}
F--Yes-->G[Upcoming]
A-->H{Submitted and Pending?}
H--Yes-->I[Review pending]
A-->J{Needs Revision?}
J--Yes-->K[Revision follow-up]
```
## Attendance
```mermaid
flowchart TD
A[Select intern/date]-->B[Validate status]-->C{Valid?}
C--No-->D[Error]
C--Yes-->E[Upsert unique intern/date]-->F[Audit]-->G[Recalculate]
```
## Reports
```mermaid
flowchart TD
A[Select report]-->B[Apply user scope]-->C{Rows?}
C--No-->D[No records message]
C--Yes-->E[Build output]
D-->F[Export PDF/CSV]
E-->F-->G[Audit export]
```
## Limitations
Excel imports are preview-only; SMTP email scheduling is not active; restoration is an offline documented operation; the exact DIT logo was not present in the uploaded ZIP. SQLite is for demos/small teams.
