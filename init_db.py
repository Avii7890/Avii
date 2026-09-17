"""Create all database tables. Run once after the MySQL schema/database exists.

Usage:
    python init_db.py
"""

from app import app
from extensions import db


def main():
    with app.app_context():
        db.create_all()
        print("All tables created (or already existed).")


if __name__ == "__main__":
    main()
