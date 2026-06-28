import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services.instantly_poller import _ingest_once

print("Running instantly poller...")
ingested = _ingest_once()
print(f"Poller done. Ingested {ingested} events.")
