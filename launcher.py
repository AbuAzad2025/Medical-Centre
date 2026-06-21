"""
Simple launcher - starts the Flask app directly on port 8080.
"""
import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ['PYTHONIOENCODING'] = 'utf-8'

from dotenv import load_dotenv
load_dotenv()

from app_factory import create_app

app = create_app()
print(f"Routes: {len(list(app.url_map.iter_rules()))}", flush=True)

host = os.environ.get('HOST', '127.0.0.1')
port = int(os.environ.get('PORT', '8080'))

app.run(host=host, port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
