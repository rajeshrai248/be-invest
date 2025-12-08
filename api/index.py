"""
Vercel serverless function entrypoint for the be-invest API.
"""
import sys
import os

# Try multiple possible paths for the be_invest package
possible_paths = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"),
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "/var/task/src",
    "/var/task",
]

for path in possible_paths:
    if path not in sys.path and os.path.exists(path):
        sys.path.insert(0, path)

# Debug: Print sys.path and check if be_invest exists
print(f"sys.path: {sys.path}")
print(f"Files in /var/task: {os.listdir('/var/task') if os.path.exists('/var/task') else 'N/A'}")
src_path = "/var/task/src"
if os.path.exists(src_path):
    print(f"Files in {src_path}: {os.listdir(src_path)}")
    be_invest_path = os.path.join(src_path, "be_invest")
    if os.path.exists(be_invest_path):
        print(f"be_invest found at {be_invest_path}")
        print(f"Contents: {os.listdir(be_invest_path)}")

try:
    from be_invest.api.server import app
    print("✅ Successfully imported app")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print(f"Current working directory: {os.getcwd()}")
    raise


