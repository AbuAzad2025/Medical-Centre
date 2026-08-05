import os
import sys

# تعيين ترميز UTF-8
if sys.platform.startswith('win'):
    os.system('chcp 65001 > nul')

from app_factory import create_app, socketio

app = create_app(os.getenv('APP_ENV'))

if __name__ == '__main__':
    env = os.getenv('APP_ENV', 'development')
    host = '0.0.0.0' if env == 'production' else '127.0.0.1'
    port = int(os.getenv('PORT', '8080'))

    try:
        socketio.run(app, debug=(env != 'production'), host=host, port=port, use_reloader=False)
    except KeyboardInterrupt:
        pass
    except Exception:
        pass
