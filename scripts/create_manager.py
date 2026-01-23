"""
سكريبت لإنشاء حساب مدير
Create Manager Account Script
"""

from app_factory import create_app, db
from models.user import User

app = create_app()

with app.app_context():
    # التحقق من وجود حساب مدير
    manager = User.query.filter_by(username='manager').first()
    
    if manager:
        print("✅ حساب المدير موجود بالفعل!")
        print(f"   Username: {manager.username}")
        print(f"   Email: {manager.email}")
        print(f"   Role: {manager.role}")
        print(f"   Active: {manager.is_active}")
    else:
        # إنشاء حساب مدير جديد
        manager = User(
            username='manager',
            email='manager@medical.com',
            full_name='مدير المركز',
            role='manager',
            department_id=None,
            is_admin=False,
            is_active=True
        )
        manager.set_password('Manager@12345')
        
        db.session.add(manager)
        db.session.commit()
        
        print("✅ تم إنشاء حساب المدير بنجاح!")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("📋 بيانات الدخول:")
        print(f"   Username: manager")
        print(f"   Password: Manager@12345")
        print(f"   Email: manager@medical.com")
        print(f"   Role: manager")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # عرض جميع المستخدمين
    print("\n📊 جميع المستخدمين في النظام:")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    all_users = User.query.all()
    for user in all_users:
        print(f"  • {user.username} ({user.role}) - {user.full_name}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

