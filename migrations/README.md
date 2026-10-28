# Review database schema

The `Review` SQLAlchemy model in `reviews_system.py` is the schema source of truth.
At startup the Flask application calls `reviews_db.create_all()` to create the `reviews`
table if it does not exist. This is suitable for the initial project integration.
For future schema changes, introduce Alembic/Flask-Migrate migrations rather than
relying on `create_all()` to alter existing columns.

The table contains reviewer name, overall rating, JSON feature ratings, comments,
recommendation, feedback category, sentiment and summary, publication/review moderation
flags, UTC submission time, and helpful/not-helpful counts.
