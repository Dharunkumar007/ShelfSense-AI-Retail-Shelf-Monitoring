"""Run with: python -m scripts.create_admin"""
from getpass import getpass
from sqlalchemy import insert, select
from backend.security import hash_password
from backend.storage import engine, init_db, users


def main():
    init_db()
    username = input("Admin username: ").strip()
    password = getpass("Password (at least 12 characters): ")
    if not 1 <= len(username) <= 80 or not 12 <= len(password) <= 256:
        raise SystemExit("Invalid username or password length.")
    if password != getpass("Confirm password: "):
        raise SystemExit("Passwords do not match.")
    with engine.begin() as conn:
        if conn.scalar(select(users.c.id).where(users.c.username == username)):
            raise SystemExit("Username already exists.")
        conn.execute(insert(users).values(username=username, password=hash_password(password), role="admin"))
    print("Administrator created. Sign in through the website.")


if __name__ == "__main__":
    main()
