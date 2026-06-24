import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
load_dotenv()

from main import app

print("Registered Routes:")
for route in app.routes:
    methods = getattr(route, "methods", None)
    methods_str = ",".join(methods) if methods else ""
    print(f"{methods_str:10} {route.path}")
