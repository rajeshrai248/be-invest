"""
Vercel serverless function entrypoint for the be-invest API.
This file exports the FastAPI app for Vercel's Python runtime.
"""
from be_invest.api.server import app

# Vercel expects the ASGI application to be named 'app'
# This is already defined in be_invest.api.server, so we just import it

