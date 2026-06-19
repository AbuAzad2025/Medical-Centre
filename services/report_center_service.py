from datetime import datetime, date, timedelta, timezone
from sqlalchemy import func, and_, desc
from app_factory import db


class ReportCenterService:
    @staticmethod
    def _parse_dates(start_raw, end_raw):
        try:
            start_date = datetime.strptime((start_raw or '').strip(), '%Y-%m-%d').date() if start_raw else (date.today() - timedelta(days=30))
        except Exception:
            start_date = date.today() - timedelta(days=30)
        try:
            end_date = datetime.strptime((end_raw or '').strip(), '%Y-%m-%d').date() if end_raw else date.today()
        except Exception:
            end_date = date.today()
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
        return start_date, end_date, start_dt, end_dt

    @staticmethod
    def compare_periods(a_start, a_end, b_start, b_end, department_id=None):
        from models.visit import Visit
        from models.payment import Payment

        def _range_metrics(start_dt, end_dt):
            vq = Visit.query.filter(Visit.created_at >= start_dt, Visit.created_at <= end_dt)
            pq = Payment.query.filter(Payment.created_at >= start_dt, Payment.created_at <= end_dt)
            if department_id:
                try:
                    dep_id = int(department_id)
                    vq = vq.filter(Visit.department_id == dep_id)
                    pq = pq.join(Visit, Visit.id == Payment.visit_id).filter(Visit.department_id == dep_id)
                except Exception:
                    pass
            visits = vq.count()
            revenue = pq.with_entities(func.sum(Payment.amount)).scalar() or 0
            return {'visits': int(visits), 'revenue': float(revenue)}

        a = _range_metrics(a_start, a_end)
        b = _range_metrics(b_start, b_end)
        delta = {
            'visits': a['visits'] - b['visits'],
            'revenue': round(a['revenue'] - b['revenue'], 2),
        }
        pct = {
            'visits': round((delta['visits'] / b['visits'] * 100), 2) if b['visits'] else None,
            'revenue': round((delta['revenue'] / b['revenue'] * 100), 2) if b['revenue'] else None,
        }
        return {'a': a, 'b': b, 'delta': delta, 'pct': pct}

    @staticmethod
    def department_transfers(start_dt, end_dt):
        from models.visit_transfer import VisitTransferLog
        from models.department import Department

        rows = db.session.query(
            VisitTransferLog.from_department_id.label('from_department_id'),
            VisitTransferLog.to_department_id.label('to_department_id'),
            func.count(VisitTransferLog.id).label('cnt')
        ).filter(
            VisitTransferLog.created_at >= start_dt,
            VisitTransferLog.created_at <= end_dt
        ).group_by(
            VisitTransferLog.from_department_id,
            VisitTransferLog.to_department_id
        ).order_by(desc(func.count(VisitTransferLog.id))).all()

        dep_ids = set()
        for r in rows:
            if r.from_department_id:
                dep_ids.add(r.from_department_id)
            if r.to_department_id:
                dep_ids.add(r.to_department_id)
        deps = {}
        if dep_ids:
            for d in Department.query.filter(Department.id.in_(list(dep_ids))).all():
                deps[d.id] = d.name_ar or d.name

        out = []
        for r in rows:
            out.append({
                'from': deps.get(r.from_department_id) or 'غير محدد',
                'to': deps.get(r.to_department_id) or 'غير محدد',
                'count': int(r.cnt or 0),
            })
        return out

    @staticmethod
    def booking_report(start_dt, end_dt):
        from models.online_booking import OnlineBooking

        q = OnlineBooking.query.filter(OnlineBooking.created_at >= start_dt, OnlineBooking.created_at <= end_dt)
        total = q.count()
        by_status = {}
        for st in ['pending', 'confirmed', 'cancelled', 'completed', 'no_show']:
            by_status[st] = q.filter(OnlineBooking.status == st).count()
        attended = by_status.get('completed', 0)
        no_show = by_status.get('no_show', 0)
        booked = total - by_status.get('cancelled', 0)
        attendance_rate = round((attended / booked * 100), 2) if booked else 0
        no_show_rate = round((no_show / booked * 100), 2) if booked else 0
        top_departments = db.session.query(
            OnlineBooking.department_id,
            func.count(OnlineBooking.id).label('cnt')
        ).filter(
            OnlineBooking.created_at >= start_dt,
            OnlineBooking.created_at <= end_dt
        ).group_by(OnlineBooking.department_id).order_by(desc(func.count(OnlineBooking.id))).limit(10).all()

        top_doctors = db.session.query(
            OnlineBooking.doctor_id,
            func.count(OnlineBooking.id).label('cnt')
        ).filter(
            OnlineBooking.created_at >= start_dt,
            OnlineBooking.created_at <= end_dt,
            OnlineBooking.doctor_id.isnot(None)
        ).group_by(OnlineBooking.doctor_id).order_by(desc(func.count(OnlineBooking.id))).limit(10).all()

        return {
            'total': int(total),
            'by_status': by_status,
            'attendance_rate': attendance_rate,
            'no_show_rate': no_show_rate,
            'top_departments': [(int(r.department_id or 0), int(r.cnt or 0)) for r in top_departments],
            'top_doctors': [(int(r.doctor_id or 0), int(r.cnt or 0)) for r in top_doctors],
        }

    @staticmethod
    def emergency_stage_times(start_dt, end_dt):
        from models.emergency_status_history import EmergencyStatusHistory
        from models.emergency import EmergencyCase

        case_ids = [r[0] for r in db.session.query(EmergencyCase.id).filter(
            EmergencyCase.created_at >= start_dt,
            EmergencyCase.created_at <= end_dt
        ).all()]
        if not case_ids:
            return {'avg_minutes': {}, 'cases': 0}

        history = EmergencyStatusHistory.query.filter(EmergencyStatusHistory.emergency_id.in_(case_ids)).order_by(
            EmergencyStatusHistory.emergency_id.asc(),
            EmergencyStatusHistory.created_at.asc()
        ).all()

        per_stage = {}
        counts = {}
        last_by_case = {}
        for h in history:
            prev = last_by_case.get(h.emergency_id)
            if prev and prev.created_at and h.created_at and prev.to_status:
                mins = int((h.created_at - prev.created_at).total_seconds() // 60)
                per_stage[prev.to_status] = per_stage.get(prev.to_status, 0) + mins
                counts[prev.to_status] = counts.get(prev.to_status, 0) + 1
            last_by_case[h.emergency_id] = h

        avg = {}
        for st, total_m in per_stage.items():
            avg[st] = round(total_m / counts.get(st, 1), 2)
        return {'avg_minutes': avg, 'cases': len(set(case_ids))}

    @staticmethod
    def radiology_revision_rate(start_dt, end_dt):
        from models.radiology_result import RadiologyResult

        q = RadiologyResult.query.filter(RadiologyResult.created_at >= start_dt, RadiologyResult.created_at <= end_dt)
        reviewed = q.filter(RadiologyResult.reviewed_at.isnot(None)).count()
        revised = q.filter(RadiologyResult.reviewed_at.isnot(None), RadiologyResult.revised_after_review == True).count()
        rate = round((revised / reviewed * 100), 2) if reviewed else 0
        return {'reviewed': int(reviewed), 'revised_after_review': int(revised), 'rate': rate}

    @staticmethod
    def capacity_impact(start_date, end_date):
        from models.user import User, StaffWorkSchedule, StaffAbsence
        from models.department import Department

        start = start_date
        end = end_date
        days = []
        cur = start
        while cur <= end:
            days.append(cur)
            cur = cur + timedelta(days=1)

        users = User.query.filter(User.role.in_(['doctor', 'lab', 'radiology'])).all()
        dept_names = {d.id: (d.name_ar or d.name) for d in Department.query.all()}

        by_dept = {}
        for u in users:
            dept_id = getattr(u, 'department_id', None) or 0
            key = dept_id
            if key not in by_dept:
                by_dept[key] = {'department': dept_names.get(dept_id) or 'غير محدد', 'scheduled_hours': 0.0, 'absence_hours': 0.0}

            schedules = StaffWorkSchedule.query.filter_by(user_id=u.id, is_active=True).all()
            sched_by_dow = {s.day_of_week: s for s in schedules}

            absences = StaffAbsence.query.filter(
                StaffAbsence.user_id == u.id,
                StaffAbsence.end_date >= start,
                StaffAbsence.start_date <= end
            ).all()
            absence_days = set()
            for a in absences:
                a_start = max(start, a.start_date)
                a_end = min(end, a.end_date)
                d = a_start
                while d <= a_end:
                    absence_days.add(d)
                    d = d + timedelta(days=1)

            for d in days:
                sched = sched_by_dow.get(d.weekday())
                if not sched:
                    continue
                h = (datetime.combine(d, sched.end_time) - datetime.combine(d, sched.start_time)).total_seconds() / 3600.0
                if h <= 0:
                    continue
                by_dept[key]['scheduled_hours'] += h
                if d in absence_days:
                    by_dept[key]['absence_hours'] += h

        out = []
        for _, v in by_dept.items():
            scheduled = float(v['scheduled_hours'] or 0)
            absent = float(v['absence_hours'] or 0)
            impact = round((absent / scheduled * 100), 2) if scheduled else 0
            out.append({
                'department': v['department'],
                'scheduled_hours': round(scheduled, 2),
                'absence_hours': round(absent, 2),
                'impact_percent': impact
            })
        out.sort(key=lambda x: x['impact_percent'], reverse=True)
        return out

