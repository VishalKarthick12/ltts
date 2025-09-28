# LTTS - Question Bank & Test Management System

A modern, full-stack web application for managing question banks, creating tests, and tracking student performance with real-time analytics.

## Features

### Authentication & User Management
- Secure JWT-based authentication
- Admin and student role management
- Session persistence and auto-logout

## Architecture

- Frontend: `frontend/` (Next.js + React Query + Tailwind)
- Backend: `backend/` (FastAPI + asyncpg)
- Database: PostgreSQL (Supabase-friendly). Tables include tests, questions, test_sessions, test_submissions, and sharing tables: test_invites, test_public_links, test_link_usage.

## Prerequisites

- Node 18+
- Python 3.10+
- PostgreSQL with a DATABASE_URL

## Environment Variables

Frontend (`frontend/.env.local`):

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```
Backend (`backend/.env`):

```
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME
JWT_SECRET=your-secure-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
## Setup

1. Install dependencies
   - Frontend
     ```bash
     npm install
     ```
   - Backend (inside `backend/`)
     ```bash
     pip install -r requirements.txt
     ```
2. Run database migrations for sharing (idempotent)
   - Inside `backend/`:
     ```bash
     python add_test_sharing.py
     ```
   - This creates tables: `test_invites`, `test_public_links`, `test_link_usage` and adds `invite_token` and `is_passed` columns to `test_sessions`/`test_submissions` as needed.
3. Login and create a test
   - Create a question bank, add questions, and generate a test.
4. Share a test
   - Go to `Dashboard → Test Management` and click `Share` on one of your tests.
   - Copy the link and open it in an incognito window to simulate a guest.
   - If logged in: you can take it directly.
   - If not logged in: enter Name + Email to proceed.
6. View analytics
   - Go to `Dashboard → Analytics`.
   - Select your test, adjust filters, view submissions and the leaderboard.
   - Export CSV if needed.

## Key Endpoints

- Test sharing
  - `POST /api/tests/{test_id}/share` – generate or reuse an active public link
  - `GET /api/tests/share/{token}` – validate token and return test details
  - `POST /api/tests/share/{token}/submit` – submit answers from a shared link (guest-friendly)
- Test taking
  - `POST /api/test-taking/{test_id}/start` – start session (accepts `invite_token`)
  - `GET /api/test-taking/{test_id}/questions?session_token=...` – get questions for session
  - `POST /api/test-taking/session/{session_token}/save-answer` – autosave answers
  - `POST /api/test-taking/session/{session_token}/submit` – submit and score

- Admin analytics
  - `GET /api/tests/{test_id}/submissions` – submissions with filters (creator only)
  - `GET /api/tests/{test_id}/leaderboard` – best scores per user/email (creator only)
  - `GET /api/tests/{test_id}/export` – CSV export

## Notes on Security and Access

- Only the test creator can generate share links, view submissions, and view the leaderboard.
- Private tests are accessible via valid `invite_token` for sessions started from a share link.
- Guest users are auto-created with a secure random password hash when they provide Name + Email.
- Share tokens use `secrets.token_urlsafe(16)` for high entropy; optional expiry and max uses are supported by schema.

## Troubleshooting

- Failed to generate share link
  - Ensure you are logged in and are the creator of the test.
  - Frontend attaches Authorization header automatically; confirm `NEXT_PUBLIC_API_URL` is correct.
  - Run `python backend/add_test_sharing.py` to ensure required tables exist.
- Questions not loading (spinner) for shared/private tests
  - The session must be started with `invite_token` included. The frontend page sends this automatically when a `token` is present in the URL.
- Analytics/Leaderboard not updating
  - Submissions are inserted with `is_passed`, and the leaderboard aggregates best scores per user/email.
  - Try refreshing the Analytics page after submitting.
  - Ensure you selected a test you created in the Analytics filter.
- Database errors about missing columns
  - Re-run the migration script: `python backend/add_test_sharing.py`.

## Project Structure Highlights

- Frontend pages
  - `frontend/src/app/dashboard/tests/page.tsx` – Test management + Share modal
  - `frontend/src/app/test/[testId]/page.tsx` – Test-taking (supports `token` query param)
  - `frontend/src/app/dashboard/analytics/page.tsx` – Admin Analytics (submissions, leaderboard, export)
- Backend routers
  - `backend/app/routers/tests.py` – Test management, sharing, analytics, export, leaderboard
  - `backend/app/routers/test_taking.py` – Session-based test-taking flow
- Migrations
  - `backend/add_test_sharing.py` – Creates sharing tables and columns; safe to run multiple times

## Roadmap

- Optional link expiry UI and max-uses controls in Share modal
- Pagination and charts in Analytics
- Role-based access for organizations/teams

---
If you encounter any issues or want to add features, please open an issue or reach out.
