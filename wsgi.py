"""
Production WSGI Entry Point for Medical System
Usage:
    gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
    uvicorn wsgi:app --host 0.0.0.0 --port 8000 --workers 4
"""

import os
import sys

# Ensure the project root is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env before any config imports
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Set required environment variables for production
os.environ.setdefault('APP_ENV', 'production')
os.environ.setdefault('FLASK_DEBUG', '0')
os.environ.setdefault('SUPPRESS_DEPRECATION_WARNINGS', '1')

from app_factory import create_app
from config import config as app_config

_env = os.environ.get('APP_ENV', 'production')
# Only honor known config names; anything else falls back to production.
if _env not in app_config:
    _env = 'production'

app = create_app(_env)

if __name__ == '__main__':
    # Development only - use gunicorn/uvicorn in production
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)), debug=False)
