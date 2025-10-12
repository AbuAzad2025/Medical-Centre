"""اختبار دالة تعديل المستخدم"""
from app_factory import create_app, db
from models.user import User

app = create_app()

with app.app_context():
    # اختبار جلب المستخدم
    user_id = 3
    user = User.query.filter_by(id=user_id).first()
    
    if user:
        print(f"✅ المستخدم موجود:")
        print(f"   ID: {user.id}")
        print(f"   Username: {user.username}")
        print(f"   Full Name: {user.full_name}")
        print(f"   Role: {user.role}")
        print(f"   Is Active: {user.is_active}")
    else:
        print(f"❌ المستخدم {user_id} غير موجود")
        
    # عرض جميع المستخدمين
    print("\n📋 جميع المستخدمين:")
    all_users = User.query.all()
    for u in all_users:
        print(f"   {u.id}: {u.username} - {u.full_name} ({u.role})")

