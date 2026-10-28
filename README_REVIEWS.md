# Market Mind— User Reviews System

## Local setup (VS Code / Windows PowerShell)

1. Extract the ZIP and open the project folder in VS Code.
2. Create and activate a virtual environment:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install packages:
   ```powershell
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env`. Set a random `SECRET_KEY`, `REVIEWS_ADMIN_USER`, and a strong `REVIEWS_ADMIN_PASSWORD`. Leave `DATABASE_URL` blank to use local `reviews.db` (SQLite). Never commit `.env`.
5. Optional sentiment analysis: install Ollama, pull the model configured by `OLLAMA_MODEL` (default `llama3.2:3b`), and ensure the Ollama service is running. If it is unavailable, reviews are still saved.
6. Start the existing Flask application:
   ```powershell
   python app.py
   ```
7. Open `http://127.0.0.1:5000`. Choose **Rate Market Mind** or visit `/reviews`.
8. Admin: visit `/admin/reviews/login`, sign in with `REVIEWS_ADMIN_USER` and `REVIEWS_ADMIN_PASSWORD`, then use `/admin/reviews`.

## PostgreSQL setup

Create a PostgreSQL database and set `DATABASE_URL` to its connection URL. Example shape:
`postgresql://USER:PASSWORD@HOST:5432/DATABASE`
The application converts common `postgres://` and `postgresql://` URLs to the psycopg 3 SQLAlchemy driver format. Database schema is created automatically at startup. For production schema evolution, use the migration notes in `migrations/README.md`.

## Render deployment

1. Push the project to a private or public GitHub repository only after checking that `.env`, passwords, API keys, and local databases are not committed.
2. In Render, create a managed PostgreSQL database and copy its **internal** connection URL when the web service and database are in the same Render region.
3. Create or update a Render Web Service connected to the repository. Build command: `pip install -r requirements.txt`. Start command: `gunicorn app:app`.
4. Add environment variables in Render: `SECRET_KEY` (long random value), `DATABASE_URL` (Render PostgreSQL URL), `REVIEWS_ADMIN_USER`, `REVIEWS_ADMIN_PASSWORD`, `OLLAMA_URL`, and `OLLAMA_MODEL`. Do not put secrets in source code.
5. Redeploy, then test `/reviews`, submit a review, and check `/admin/reviews`.
6. Keep the database and web service in compatible regions. Use the database's persistent managed storage; local SQLite on an ephemeral web-service filesystem is only a development fallback and is not suitable for preserving production reviews.

## How to view teacher/classmate reviews

Share the deployed `/reviews` page with your teacher and classmates. They can submit a review without creating an account. Their review is stored but stays private until you sign in at `/admin/reviews/login`, inspect it, and click **Approve & publish**. All submitted reviews (published or not) appear in the private admin dashboard. Export the full dataset using **Export CSV**.

## Features and privacy

- Overall 1–5 star rating and optional feature ratings, comments, optional name, recommendation, and category (general / bug / feature request).
- Server-side validation and persistent database storage.
- Private dashboard with aggregate statistics, filters, sorting, pagination, moderation, deletion, and CSV export.
- Public page displays only administrator-approved reviews. Anonymous names are shown as “Anonymous”; reviewer details are not shown.
- Helpful voting uses a browser cookie to reduce repeat votes. It is not strong identity-based anti-abuse protection.
- Ollama sentiment classification is best-effort and approximate. If Ollama is unreachable, collection continues and the dashboard reports unavailable sentiment.
- The common suggestions summary is a transparent frequency-based summary of comment terms; it does not invent user feedback.

## Hosting plan note

Render plan features, free PostgreSQL availability, expiration/retention rules, and storage quotas can change. Check current Render plan details before relying on a free database for long-term review retention. For reviews that must persist, use a currently supported persistent PostgreSQL service and maintain backups.

## Testing

Run `python -m compileall app.py reviews_system.py`, then start the app and submit a review, log in as admin, approve it, confirm it appears publicly, and export CSV. Automated integration tests require dependencies and a running database.
