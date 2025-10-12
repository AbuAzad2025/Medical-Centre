"""
خادم إنتاجي خفيف باستخدام Waitress (يناسب ويندوز).
يشغّل التطبيق على البورت المحدد عبر متغير PORT أو 5001 افتراضيًا.
"""
import os
from waitress import serve
from app_factory import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    host = os.environ.get("HOST", "0.0.0.0")
    serve(app, host=host, port=port)
