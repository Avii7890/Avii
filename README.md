# Daily Habit Admin

A Flask + MySQL admin website for tracking daily habits/tasks by time slot:
mark each task pending / completed / failed (with a reason), record what to
do better tomorrow, and view hourly, daily, weekly and yearly reports.

## Features

- Admin login (hashed passwords, Flask-Login sessions)
- Tasks scheduled by time slot, auto-rolled into a fresh log each day
- Mark a task completed or failed; failures capture a reason and an
  "improvement for tomorrow" note
- Per-day reflection notes
- Reports: Hourly breakdown, Daily table, Weekly chart + table,
  Yearly chart + table (completion rate per month)
- MySQL storage via SQLAlchemy

## Setup

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create the MySQL database

Edit the username/password in `schema.sql`, then run it as a MySQL admin:

```bash
mysql -u root -p < schema.sql
```

(This only creates the database + user; tables are created by `init_db.py`
below, so the CREATE TABLE statements in `schema.sql` are optional/reference.)

### 3. Configure environment variables

```bash
cp .env.example .env
# edit .env with your DB credentials and a real SECRET_KEY
```

### 4. Create tables and the first admin account

```bash
python init_db.py
python create_admin.py
```

`create_admin.py` prompts for a username/password (min 8 chars) and stores
a salted hash — no plaintext passwords are ever stored.

### 5. Run the app

```bash
python app.py
```

Visit http://localhost:5000, log in, then go to **Tasks** to add your daily
habits with their time slots (e.g. 06:00 Workout, 09:00 Deep work, 22:00
Read). Each day the **Dashboard** shows that day's tasks so you can mark
them complete/failed as you go, and **Reports** gives hourly/daily/weekly/
yearly views.

## Project layout

```
app.py            Flask app + routes
config.py         Env-based configuration (DB URI, secret key)
extensions.py     SQLAlchemy / Flask-Login instances
models.py         Admin, Task, TaskLog, DailyReflection
init_db.py        Creates tables from models.py
create_admin.py   CLI to create/reset an admin login
schema.sql        Reference SQL (database/user + table DDL)
templates/        Jinja2 templates (Bootstrap 5 + Chart.js)
static/           CSS
tests/            Pytest suite (uses in-memory SQLite, no MySQL needed)
.github/workflows/ci.yml   GitHub Actions: lint + tests on every push/PR
```

## Running tests / CI

The test suite doesn't need MySQL — it swaps in an in-memory SQLite database.

```bash
pip install -r requirements-dev.txt
pytest -v
```

A GitHub Actions workflow (`.github/workflows/ci.yml`) runs the same lint +
test steps automatically on every push and pull request, so breakage is
caught before you pull the branch down to run it locally.
