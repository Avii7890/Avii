"""Create or update an admin account.

Usage:
    python create_admin.py
"""

import getpass

from app import app
from extensions import db
from models import Admin


def main():
    with app.app_context():
        username = input("Admin username: ").strip()
        if not username:
            print("Username cannot be empty.")
            return

        password = getpass.getpass("Admin password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.")
            return
        if len(password) < 8:
            print("Password should be at least 8 characters.")
            return

        admin = Admin.query.filter_by(username=username).first()
        if admin:
            admin.set_password(password)
            db.session.commit()
            print(f'Password updated for existing admin "{username}".')
        else:
            admin = Admin(username=username)
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            print(f'Admin "{username}" created.')


if __name__ == "__main__":
    main()
