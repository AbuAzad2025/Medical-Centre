# -*- coding: utf-8 -*-
import sys
import os

# تعيين ترميز UTF-8
if sys.platform.startswith('win'):
    os.system('chcp 65001 > nul')

from app_factory import create_app
app = create_app()

if __name__ == '__main__':
    print("=" * 60)
    print("Medical System - النظام الصحي المتكامل")
    print("=" * 60)
    print("Server: http://127.0.0.1:5001")
    print("Development Mode: Enabled")
    print("=" * 60)
    print("System Ready!")
    print("=" * 60)
    
    try:
        app.run(debug=True, host='127.0.0.1', port=5001, use_reloader=False)
    except KeyboardInterrupt:
        print("\nSystem stopped by user")
    except Exception as e:
        print(f"\nError starting system: {e}")
