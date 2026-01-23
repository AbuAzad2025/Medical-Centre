# -*- coding: utf-8 -*-
import sys
import os

# تعيين ترميز UTF-8
if sys.platform.startswith('win'):
    os.system('chcp 65001 > nul')

from app_factory import create_app, socketio
app = create_app(os.getenv('APP_ENV'))

if __name__ == '__main__':
    print("=" * 60)
    print("Medical System - النظام الصحي المتكامل")
    print("=" * 60)
    env = os.getenv('APP_ENV', 'development')
    host = '0.0.0.0' if env == 'production' else '127.0.0.1'
    port = int(os.getenv('PORT', '5001'))
    print(f"Server: http://{host}:{port}")
    print("Production Mode: Enabled" if env == 'production' else "Development Mode: Enabled")
    print("=" * 60)
    print("System Ready!")
    print("=" * 60)
    
    try:
        socketio.run(app, debug=(env != 'production'), host=host, port=port, use_reloader=False)
    except KeyboardInterrupt:
        print("\nSystem stopped by user")
    except Exception as e:
        print(f"\nError starting system: {e}")
