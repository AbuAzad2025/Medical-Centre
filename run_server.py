"""
تشغيل السيرفر مع لوجز واضحة
"""
import sys
import logging
from app_factory import create_app

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
        logger.info("🌐 السيرفر يعمل على: http://127.0.0.1:5001")
        logger.info("=" * 60)
        
        app.run(
            host='127.0.0.1',
            port=5001,
            debug=True,
            use_reloader=False  # لمنع إعادة التشغيل التلقائي
        )
        
    except Exception as e:
        logger.error(f"❌ خطأ في تشغيل السيرفر: {str(e)}", exc_info=True)
        sys.exit(1)

