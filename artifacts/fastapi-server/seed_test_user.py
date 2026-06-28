"""Seed the test user and assign the Freshdesk product profile.

Run:  python seed_test_user.py
"""
from dotenv import load_dotenv
load_dotenv()

from app.db import init_db, SessionLocal, User, Strategy, gen_id
from app.crypto import hash_password
from app.services import settings_service
import os

TEST_EMAIL = "saipraneethacxelinagentix@gmail.com"
TEST_PASSWORD = "Test@1234"


def main():
    init_db()
    db = SessionLocal()
    try:
        # 1. Create or fetch the test user
        user = db.query(User).filter(User.email == TEST_EMAIL).first()
        if user is None:
            user = User(
                id=gen_id(),
                email=TEST_EMAIL,
                password_hash=hash_password(TEST_PASSWORD),
                is_admin=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created user: {TEST_EMAIL} (id={user.id})")
        else:
            # Update password in case it changed
            user.password_hash = hash_password(TEST_PASSWORD)
            db.commit()
            print(f"User already exists: {TEST_EMAIL} (id={user.id})")

        # 2. Create or assign the Freshdesk strategy
        freshdesk = (
            db.query(Strategy)
            .filter(Strategy.product_name == "Freshdesk by Freshworks")
            .first()
        )
        if freshdesk is None:
            freshdesk = Strategy(
                user_id=user.id,
                product_name="Freshdesk by Freshworks",
                description=(
                    "Freshdesk is a cloud-based customer support software that helps "
                    "businesses manage customer tickets across email, phone, chat, "
                    "social media, and messaging."
                ),
                target_market="Mid-market and enterprise B2B SaaS companies in India, North America, and Asia-Pacific",
                pain_points_raw=(
                    "Support teams drown in ticket volume with no way to prioritize. "
                    "Agents waste time switching between email, chat, and phone tools. "
                    "Managers have zero visibility into SLA compliance."
                ),
                status="draft",
            )
            db.add(freshdesk)
            db.commit()
            db.refresh(freshdesk)
            print(f"Created strategy: Freshdesk by Freshworks (id={freshdesk.id})")
        else:
            # Assign to the test user if unassigned
            if freshdesk.user_id is None or freshdesk.user_id == "user_public":
                freshdesk.user_id = user.id
                db.commit()
                print(f"Assigned existing Freshdesk strategy to {TEST_EMAIL}")
            else:
                print(f"Freshdesk strategy already assigned to user_id={freshdesk.user_id}")

        # 3. Also assign any existing unowned strategies to this user
        unowned = (
            db.query(Strategy)
            .filter(
                (Strategy.user_id == None) | (Strategy.user_id == "user_public")
            )
            .all()
        )
        for s in unowned:
            s.user_id = user.id
            print(f"  Assigned orphan strategy '{s.product_name}' to {TEST_EMAIL}")
        if unowned:
            db.commit()

        # 4. Auto-configure API keys for the new user
        for name, env_var in [("apollo", "APOLLO_API_KEY"), ("instantly", "INSTANTLY_API_KEY")]:
            key = os.environ.get(env_var)
            if key:
                settings_service.upsert_integration(db, user.id, name, key, is_enabled=True)
                print(f"  Configured {name} API key for {TEST_EMAIL}")

        print("\nDone! Login with:")
        print(f"  Email:    {TEST_EMAIL}")
        print(f"  Password: {TEST_PASSWORD}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
