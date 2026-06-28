"""Tests for services.smart_ai_engine.SmartAIEngine (no live network)."""

from unittest.mock import MagicMock, patch

import pytest

from services.smart_ai_engine import SmartAIEngine


@pytest.fixture
def engine(rollback_db):
    return SmartAIEngine(rollback_db)


class TestNLPHelpers:
    def test_extract_intent_analysis_users(self, engine):
        intents = engine._extract_intent('حلل أخطاء المستخدمين')
        assert 'analysis' in intents
        assert 'errors' in intents
        assert 'users' in intents

    def test_extract_entities_doctor_name(self, engine):
        entities = engine._extract_entities('ما حالة الدكتور أحمد')
        assert 'أحمد' in entities['names']

    def test_extract_entities_numbers(self, engine):
        entities = engine._extract_entities('كم عدد 25 مريض')
        assert 25 in entities['numbers']

    def test_is_calculation_detects_expression(self, engine):
        assert engine._is_calculation('احسب 5 + 3') is True
        assert engine._is_calculation('مرحبا') is False


class TestCalculation:
    def test_addition(self, engine):
        res = engine._handle_calculation('5 + 3')
        assert '8' in res['response']

    def test_division_by_zero(self, engine):
        res = engine._handle_calculation('10 / 0')
        assert 'صفر' in res['response']

    def test_calculator_prompt_without_expression(self, engine):
        res = engine._handle_calculation('احسب')
        assert 'حاسبة' in res['response'] or 'حسابية' in res['response']


class TestProcessQueryRouting:
    def test_routes_to_calculation(self, engine):
        res = engine.process_query('10 + 5')
        assert '15' in res['response']

    def test_routes_analysis_users_errors(self, engine):
        with patch.object(engine, '_analyze_user_errors', return_value={'response': 'تحليل', 'actions': []}):
            res = engine.process_query('حلل أخطاء المستخدمين')
        assert res['response'] == 'تحليل'

    def test_routes_analysis_doctors(self, engine):
        with patch.object(engine, '_analyze_doctor_problems', return_value={'response': 'أطباء', 'actions': []}):
            res = engine.process_query('حلل مشاكل الأطباء')
        assert res['response'] == 'أطباء'

    def test_routes_department_problems(self, engine):
        with patch.object(engine, '_analyze_department_problems', return_value={'response': 'أقسام', 'actions': []}):
            res = engine.process_query('مشاكل الأقسام')
        assert res['response'] == 'أقسام'

    def test_routes_count_query(self, engine):
        with patch.object(engine, '_handle_count_query', return_value={'response': 'عدد', 'actions': []}):
            res = engine.process_query('كم عدد المرضى')
        assert res['response'] == 'عدد'

    def test_routes_user_query(self, engine):
        with patch.object(engine, '_handle_user_query', return_value={'response': 'users', 'actions': []}):
            res = engine.process_query('أظهر المستخدمين')
        assert res['response'] == 'users'

    def test_routes_doctor_query(self, engine):
        with patch.object(engine, '_handle_doctor_query', return_value={'response': 'docs', 'actions': []}):
            res = engine.process_query('doctor performance report')
        assert res['response'] == 'docs'

    def test_routes_patient_query(self, engine):
        with patch.object(engine, '_handle_patient_query', return_value={'response': 'pats', 'actions': []}):
            res = engine.process_query('معلومات المريض')
        assert res['response'] == 'pats'

    def test_routes_visit_query(self, engine):
        with patch.object(engine, '_handle_visit_query', return_value={'response': 'vis', 'actions': []}):
            res = engine.process_query('زيارات اليوم')
        assert res['response'] == 'vis'

    def test_routes_appointment_query(self, engine):
        with patch.object(engine, '_handle_appointment_query', return_value={'response': 'appt', 'actions': []}):
            res = engine.process_query('مواعيد الغد')
        assert res['response'] == 'appt'

    def test_routes_service_query(self, engine):
        with patch.object(engine, '_handle_service_query', return_value={'response': 'svc', 'actions': []}):
            res = engine.process_query('الخدمات المتاحة')
        assert res['response'] == 'svc'

    def test_routes_system_analysis(self, engine):
        with patch.object(engine, '_handle_system_analysis', return_value={'response': 'sys', 'actions': []}):
            res = engine.process_query('حلل النظام')
        assert res['response'] == 'sys'

    def test_routes_report_generation(self, engine):
        with patch.object(engine, '_handle_report_generation', return_value={'response': 'rep', 'actions': []}):
            res = engine.process_query('أنشئ تقرير')
        assert res['response'] == 'rep'

    def test_routes_database_query(self, engine):
        with patch.object(engine, '_handle_database_query', return_value={'response': 'db', 'actions': []}):
            res = engine.process_query('جداول قاعدة البيانات')
        assert res['response'] == 'db'

    def test_fallback_general_search(self, engine):
        with patch.object(engine, '_handle_general_search', return_value={'response': 'search', 'actions': []}):
            res = engine.process_query('xyz غير معروف')
        assert res['response'] == 'search'

    def test_exception_returns_error_response(self, engine):
        with patch.object(engine, '_extract_intent', side_effect=RuntimeError('boom')):
            res = engine.process_query('test')
        assert 'خطأ' in res['response']


class TestAnalyzeUserErrors:
    def test_analyze_user_errors_with_data(self, engine, rollback_db):
        from models.user import User
        u = User(username='aiu_' + str(id(engine)), email='ai@test.local', full_name='AI', role='doctor', is_active=False)
        u.set_password('x')
        rollback_db.session.add(u)
        rollback_db.session.commit()
        res = engine._analyze_user_errors()
        assert 'response' in res
        assert 'المستخدم' in res['response'] or 'مستخدم' in res['response']

    def test_analyze_doctor_problems(self, engine):
        res = engine._analyze_doctor_problems()
        assert 'response' in res

    def test_analyze_department_problems(self, engine):
        res = engine._analyze_department_problems()
        assert 'response' in res

    def test_handle_database_query_lists_tables(self, engine):
        engine.inspector = MagicMock()
        engine.inspector.get_table_names.return_value = ['patients', 'visits']
        res = engine._handle_database_query('ما هي الجداول')
        assert 'patients' in res['response']

    def test_handle_report_generation(self, engine):
        res = engine._handle_report_generation()
        assert 'response' in res

    def test_handle_system_analysis(self, engine):
        with patch.object(engine, '_analyze_user_errors', return_value={'response': 'u', 'actions': []}), \
             patch.object(engine, '_analyze_doctor_problems', return_value={'response': 'd', 'actions': []}), \
             patch.object(engine, '_analyze_department_problems', return_value={'response': 'dept', 'actions': []}):
            res = engine._handle_system_analysis()
        assert 'response' in res


class TestCalculationOperators:
    def test_subtraction(self, engine):
        res = engine._handle_calculation('10 - 4')
        assert '6' in res['response']

    def test_multiplication(self, engine):
        res = engine._handle_calculation('6 * 7')
        assert '42' in res['response']

    def test_division(self, engine):
        res = engine._handle_calculation('20 / 4')
        assert '5' in res['response']

    def test_unsupported_operator(self, engine):
        with patch('re.search') as mock_search:
            mock_match = MagicMock()
            mock_match.group.side_effect = lambda i: {1: '1', 2: '%', 3: '2'}[i]
            mock_search.return_value = mock_match
            res = engine._handle_calculation('1 % 2')
        assert 'غير مدعومة' in res['response']


class TestHandlerImplementations:
    """Direct handler tests against rollback DB (no network)."""

    def test_handle_count_query_patients(self, engine):
        res = engine._handle_count_query('كم عدد المرضى')
        assert 'المرضى' in res['response']

    def test_handle_count_query_all_stats_fallback(self, engine):
        res = engine._handle_count_query('كم العدد الإجمالي')
        assert 'المستخدمون' in res['response']

    def test_handle_count_query_visits_and_departments(self, engine):
        res = engine._handle_count_query('زيارة قسم خدمة موعد')
        assert 'الزيارات' in res['response']
        assert 'الأقسام' in res['response']

    def test_handle_user_query_general(self, engine):
        res = engine._handle_user_query('معلومات المستخدمين')
        assert 'المستخدمين' in res['response']

    def test_handle_user_query_name_search(self, engine, rollback_db):
        from models.user import User
        u = User(
            username='ai_search_' + str(id(engine)),
            email='search@test.local',
            full_name='SearchTarget',
            role='receptionist',
            is_active=True,
        )
        u.set_password('x')
        rollback_db.session.add(u)
        rollback_db.session.commit()
        res = engine._handle_user_query('user SearchTarget')
        assert 'SearchTarget' in res['response']

    def test_handle_doctor_query_general(self, engine):
        res = engine._handle_doctor_query('معلومات الأطباء')
        assert 'الأطباء' in res['response']

    def test_handle_doctor_query_not_found(self, engine):
        res = engine._handle_doctor_query('doctor NonexistentXYZ')
        assert 'لم يتم العثور' in res['response']

    def test_handle_patient_query_general(self, engine):
        res = engine._handle_patient_query('إحصائيات المرضى')
        assert 'المرضى' in res['response']

    def test_handle_department_query_general(self, engine):
        res = engine._handle_department_query('الأقسام')
        assert 'الأقسام' in res['response']

    def test_handle_visit_query(self, engine):
        res = engine._handle_visit_query('زيارات')
        assert 'الزيارات' in res['response']

    def test_handle_appointment_query(self, engine):
        res = engine._handle_appointment_query('مواعيد')
        assert 'المواعيد' in res['response']

    def test_handle_service_query(self, engine):
        res = engine._handle_service_query('الخدمات')
        assert 'الخدمات' in res['response']

    def test_handle_general_search(self, engine):
        res = engine._handle_general_search('anything')
        assert 'المساعد الذكي' in res['response']

    def test_handle_system_analysis_live(self, engine):
        res = engine._handle_system_analysis()
        assert 'تحليل شامل' in res['response']

    def test_process_query_end_to_end_count(self, engine):
        res = engine.process_query('كم عدد المرضى')
        assert 'response' in res

    def test_process_query_end_to_end_general(self, engine):
        res = engine.process_query('مرحبا غير معروف')
        assert 'المساعد الذكي' in res['response']


class TestAnalyzeWithFixtureData:
    def test_analyze_doctor_problems_with_inactive_doctor(self, engine, rollback_db):
        from models.user import User
        d = User(
            username='aidoc_' + str(id(engine)),
            email='doc@test.local',
            full_name='Inactive Doc',
            role='doctor',
            is_active=False,
        )
        d.set_password('x')
        rollback_db.session.add(d)
        rollback_db.session.commit()
        res = engine._analyze_doctor_problems()
        assert 'غير نشط' in res['response']

    def test_analyze_department_problems_inactive_dept(self, engine, rollback_db, test_tenant):
        from models.department import Department
        dept = Department(
            name='AI Inactive Dept ' + str(id(engine)),
            name_ar='قسم غير نشط',
            description='test',
            is_active=False,
            tenant_id=test_tenant.id,
        )
        rollback_db.session.add(dept)
        rollback_db.session.commit()
        res = engine._analyze_department_problems()
        assert 'غير نشط' in res['response']

    def test_handle_database_query_with_columns(self, engine):
        engine.inspector = MagicMock()
        engine.inspector.get_table_names.return_value = ['users']
        engine.inspector.get_columns.return_value = [{'name': 'id'}, {'name': 'email'}]
        res = engine._handle_database_query('جداول قاعدة البيانات')
        assert 'users' in res['response']
        assert '2 عمود' in res['response']

    def test_handle_doctor_query_by_name(self, engine):
        from models.user import User
        from models.visit import Visit
        mock_doctor = MagicMock()
        mock_doctor.full_name = 'Named Doctor'
        mock_doctor.specialization = 'General'
        mock_doctor.department = None
        mock_doctor.is_active = True
        mock_doctor.id = 999
        with patch.object(User, 'query') as uq:
            uq.filter.return_value.all.return_value = [mock_doctor]
            with patch.object(Visit, 'query') as vq:
                vq.filter_by.return_value.count.return_value = 0
                vq.filter.return_value.count.return_value = 0
                res = engine._handle_doctor_query('doctor Named')
        assert 'Named Doctor' in res['response']

    def test_handle_department_query_by_name(self, engine, rollback_db, test_tenant):
        from models.department import Department
        dept = Department(
            name='Cardiology ' + str(id(engine)),
            name_ar='قلب',
            description='heart',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        rollback_db.session.add(dept)
        rollback_db.session.commit()
        res = engine._handle_department_query('department Cardiology')
        assert 'Cardiology' in res['response']

    def test_analyze_user_errors_comprehensive(self, engine, rollback_db):
        from models.user import User
        users = [
            User(username='aie1_' + str(id(engine)), email='', full_name='No Email', role='nurse', is_active=True),
            User(username='aie2_' + str(id(engine)), email='e2@test.local', full_name='No Login', role='admin', is_active=True),
            User(username='aie3_' + str(id(engine)), email='e3@test.local', full_name='No Role', role='', is_active=True),
            User(username='aie4_' + str(id(engine)), email='e4@test.local', full_name='No Dept Doc', role='doctor', is_active=True),
        ]
        for u in users:
            u.set_password('x')
            rollback_db.session.add(u)
        rollback_db.session.commit()
        res = engine._analyze_user_errors()
        assert 'response' in res
        assert 'المستخدمين' in res['response'] or 'مستخدم' in res['response']

    def test_calculation_exception_handling(self, engine):
        with patch('re.search', side_effect=ValueError('parse fail')):
            res = engine._handle_calculation('5 + 3')
        assert 'خطأ' in res['response']
