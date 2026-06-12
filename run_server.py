"""
تشغيل السيرفر مع لوجز واضحة
"""
import sys
import logging
import os
from dotenv import load_dotenv

# تحميل متغيرات البيئة من .env
load_dotenv()

from app_factory import create_app, socketio
import threading, time

# إعداد logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info("🚀 بدء تشغيل النظام الطبي...")
    
    try:
        app = create_app()
        logger.info("✅ تم إنشاء التطبيق بنجاح")
        logger.info(f"📊 عدد المسارات المسجلة: {len(list(app.url_map.iter_rules()))}")
        logger.info(f"📦 عدد Blueprints: {len(app.blueprints)}")
        logger.info("🌐 السيرفر يعمل على: http://127.0.0.1:5002")
        logger.info("=" * 60)

        def _alerts_worker(flask_app):
            with flask_app.app_context():
                from services.notification_service import NotificationService
            while True:
                try:
                    with flask_app.app_context():
                        NotificationService.check_and_send_alerts()
                        logger.info("⏰ تم تنفيذ مهمة التنبيهات المجدولة")
                except Exception as e:
                    logger.error(f"خطأ في مهمة التنبيهات المجدولة: {str(e)}")
                time.sleep(3600)

        t = threading.Thread(target=_alerts_worker, args=(app,), daemon=True)
        t.start()
        logger.info("🕒 تم تفعيل مهمة التنبيهات كل ساعة")
        
        host = os.environ.get('HOST', '127.0.0.1')
        port = int(os.environ.get('PORT', '8080'))
        debug = os.environ.get('FLASK_DEBUG', 'false').lower() in ('true', '1', 'on')
        socketio.run(
            app,
            host=host,
            port=port,
            debug=debug,
            use_reloader=False
        )
        
    except Exception as e:
        logger.error(f"❌ خطأ في تشغيل السيرفر: {str(e)}", exc_info=True)
        sys.exit(1)

