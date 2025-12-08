"""
Vercel serverless function entrypoint for the be-invest API.
This file exports the FastAPI app for Vercel's Python runtime.
"""
import sys
from pathlib import Path

# Add the src directory to Python path so imports work in Vercel
root_dir = Path(__file__).parent.parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Now we can import the app
from be_invest.api.server import app

# Vercel expects the ASGI application to be named 'app'
# This is already defined in be_invest.api.server, so we just import it

