"""
Vercel serverless function entrypoint for the be-invest API.
"""
import sys
import os

# Add the src directory to Python path for Vercel deployment
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
src_dir = os.path.join(root_dir, "src")

# Add paths if they exist
for path in [src_dir, root_dir]:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

# Import the FastAPI app
from be_invest.api.server import app

# Vercel expects the ASGI application to be named 'app'
__all__ = ["app"]


