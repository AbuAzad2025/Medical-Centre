import unittest
from app_factory import create_app, db
from services.notification_service import NotificationService
from models.notification import Notification, NotificationTemplate, NotificationQueue
from models.user import User


class NotificationServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.user = User(username='notif_user', email='notif@example.com', full_name='Notif User', role='manager')
        self.user.set_password('p')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        # Use TRUNCATE TABLE instead of DROP SCHEMA to avoid enum type recreation issues
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if tables:
            db.session.execute(db.text(f"TRUNCATE TABLE {', '.join(tables)} CASCADE"))
        db.session.commit()
        db.engine.dispose()
        db.session.remove()
        self.ctx.pop()

    def test_send_notification_basic(self):
        res = NotificationService.send_notification(
            recipient_id=self.user.id,
            title='مرحبا',
            message='رسالة اختبار',
            notification_type='info'
        )
        self.assertTrue(res['success'])
        nid = res['notification_id']
        n = db.session.get(Notification, nid)
        self.assertEqual(n.title, 'مرحبا')
        self.assertEqual(n.message, 'رسالة اختبار')
        self.assertEqual(n.notification_type, 'info')

    def test_send_notification_with_template(self):
        tpl = NotificationTemplate(
            name='welcome_tpl',
            template_type='info',
            subject='مرحباً {name}',
            content='أهلاً {name} في القسم {dept}'
        )
        db.session.add(tpl)
        db.session.commit()
        res = NotificationService.send_notification(
            recipient_id=self.user.id,
            template_name='welcome_tpl',
            template_variables={'name': 'أحمد', 'dept': 'الاستقبال'}
        )
        self.assertTrue(res['success'])
        n = db.session.get(Notification, res['notification_id'])
        self.assertEqual(n.title, 'مرحباً أحمد')
        self.assertEqual(n.message, 'أهلاً أحمد في القسم الاستقبال')
        self.assertEqual(n.notification_type, 'info')

    def test_queue_add_and_process(self):
        r1 = NotificationService.add_to_notification_queue(
            user_id=self.user.id,
            notification_type='email',
            recipient='test@example.com',
            subject='موضوع',
            content='محتوى'
        )
        r2 = NotificationService.add_to_notification_queue(
            user_id=self.user.id,
            notification_type='whatsapp',
            recipient='+970000000',
            subject='',
            content='مرحبا'
        )
        self.assertTrue(r1['success'] and r2['success'])
        status_before = NotificationService.get_notification_queue_status()
        self.assertTrue(status_before['success'])
        self.assertEqual(status_before['pending_count'], 2)
        proc = NotificationService.process_notification_queue()
        self.assertTrue(proc['success'])
        status_after = NotificationService.get_notification_queue_status()
        self.assertTrue(status_after['success'])
        self.assertEqual(status_after['sent_count'], 2)


if __name__ == '__main__':
    unittest.main()
