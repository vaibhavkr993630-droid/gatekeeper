"""Provision a platform admin account.

There is no public admin-registration endpoint — admins are operators of the
platform itself, not customers, so they're created out-of-band like this.

Usage:
    python -m scripts.create_admin --email ops@gatekeeper.dev --password 'change-me'
"""
import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.admin import AdminUser


async def create_admin(email: str, password: str) -> None:
    async with SessionLocal() as db:
        existing = await db.scalar(select(AdminUser).where(AdminUser.email == email.lower()))
        if existing is not None:
            print(f"An admin with email {email!r} already exists (id={existing.id}).")
            sys.exit(1)

        admin = AdminUser(email=email.lower(), hashed_password=hash_password(password))
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        print(f"Created admin {admin.email!r} (id={admin.id}).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", help="omit to be prompted (safer: not in shell history)")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")
    if len(password) < 8:
        parser.error("password must be at least 8 characters")

    asyncio.run(create_admin(args.email, password))


if __name__ == "__main__":
    main()
