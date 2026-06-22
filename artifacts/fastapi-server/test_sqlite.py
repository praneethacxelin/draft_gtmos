import os
import sys

# Add current dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from app.db import Base

try:
    engine = create_engine("sqlite:///test_gtm.db")
    Base.metadata.create_all(bind=engine)
    print("SUCCESS: SQLite tables created!")
except Exception as e:
    print("FAILED:", str(e))
    import traceback
    traceback.print_exc()
