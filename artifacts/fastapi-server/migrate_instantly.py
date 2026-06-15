import os
from dotenv import load_dotenv
load_dotenv('.env')

from app.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text('ALTER TABLE instantly_campaigns ADD COLUMN analytics_json JSONB;'))
    conn.execute(text('ALTER TABLE instantly_campaigns ADD COLUMN daily_analytics_json JSONB;'))
    conn.execute(text('ALTER TABLE instantly_campaigns ADD COLUMN steps_analytics_json JSONB;'))
    conn.commit()
print("Migration done.")
