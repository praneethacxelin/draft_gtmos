import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from main import app

print("Registered Routes:")
for route in app.routes:
    methods = getattr(route, "methods", None)
    method_str = f"[{', '.join(methods)}]" if methods else ""
    print(f"  {method_str:15} {route.path}")
