"""
تشغيل السيرفر مع لوجز واضحة
"""

import io
import logging
import os
import sys
import threading
import time

from dotenv import load_dotenv

load_dotenv()

from app_factory import create_app, socketio

# Force UTF-8 encoding on stdout/stderr to handle emoji in log messages
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# إعداد logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info('🚀 بدء تشغيل النظام الطبي...')

    try:
        host = os.environ.get('HOST', '127.0.0.1')
        port = int(os.environ.get('PORT', '8080'))

        app = create_app()
        logger.info('✅ تم إنشاء التطبيق بنجاح')
        logger.info(f'📊 عدد المسارات المسجلة: {len(list(app.url_map.iter_rules()))}')
        logger.info(f'📦 عدد Blueprints: {len(app.blueprints)}')
        logger.info(f'🌐 السيرفر يعمل على: http://{host}:{port}')
        logger.info('=' * 60)

        def _alerts_worker(flask_app):
            from services.notification_service import NotificationService
            from services.tenant_job_runner import for_each_tenant

            while True:
                time.sleep(3600)  # delay first+every run — startup must not write data
                try:
                    for_each_tenant(
                        flask_app,
                        lambda tenant_id: NotificationService.check_and_send_alerts(
                            tenant_id=tenant_id
                        ),
                    )
                    logger.info('⏰ تم تنفيذ مهمة التنبيهات المجدولة')
                except Exception:
                    logger.exception('خطأ في مهمة التنبيهات المجدولة: %s')

        t = threading.Thread(target=_alerts_worker, args=(app,), daemon=True)
        t.start()
        logger.info('🕒 تم تفعيل مهمة التنبيهات كل ساعة')

        debug = os.environ.get('FLASK_DEBUG', 'false').lower() in ('true', '1', 'on')
        socketio.run(
            app, host=host, port=port, debug=debug, use_reloader=False, allow_unsafe_werkzeug=True
        )

    except Exception as e:
        logger.error(f'❌ خطأ في تشغيل السيرفر: {e!s}', exc_info=True)
        sys.exit(1)
