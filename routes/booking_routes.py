"""
مسارات الحجز عن بعد - Online Booking Routes
Medical System Online Booking Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models.online_booking import OnlineBooking, PaymentTransaction
from models.patient import Patient
from models.appointment import Appointment
from models.user import User
from models.department import Department
from app_factory import db
import logging
from datetime import datetime, timedelta
import json

booking_bp = Blueprint('booking', __name__)

@booking_bp.route('/booking')
def index():
    """صفحة الحجز الرئيسية"""
    try:
        # جلب الأقسام المتاحة للحجز
        departments = Department.query.filter_by(is_active=True).all()
        
        # جلب الأطباء المتاحين
        doctors = User.query.filter_by(role='doctor', is_active=True).all()
        
        return render_template('booking/index.html', 
                             departments=departments, 
                             doctors=doctors)
    except Exception as e:
        logging.error(f"Error loading booking page: {str(e)}")
        flash('حدث خطأ في تحميل صفحة الحجز', 'error')
        return redirect(url_for('main.dashboard'))

@booking_bp.route('/booking/create', methods=['GET', 'POST'])
def create_booking():
    """إنشاء حجز جديد"""
    if request.method == 'POST':
        try:
            # إنشاء حجز جديد
            booking = OnlineBooking(
                patient_name=request.form.get('patient_name'),
                patient_phone=request.form.get('patient_phone'),
                patient_email=request.form.get('patient_email'),
                department_id=request.form.get('department_id'),
                doctor_id=request.form.get('doctor_id'),
                preferred_date=datetime.strptime(request.form.get('preferred_date'), '%Y-%m-%d').date(),
                preferred_time=request.form.get('preferred_time'),
                notes=request.form.get('notes'),
                status='pending'
            )
            
            db.session.add(booking)
            db.session.commit()
            
            flash('تم إنشاء الحجز بنجاح', 'success')
            return redirect(url_for('booking.confirmation', booking_id=booking.id))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating booking: {str(e)}")
            flash(f'حدث خطأ في إنشاء الحجز: {str(e)}', 'error')
    
    # جلب البيانات المطلوبة للنموذج
    departments = Department.query.filter_by(is_active=True).all()
    doctors = User.query.filter_by(role='doctor', is_active=True).all()
    
    return render_template('booking/create.html', 
                         departments=departments, 
                         doctors=doctors)

@booking_bp.route('/booking/confirmation/<int:booking_id>')
def confirmation(booking_id):
    """تأكيد الحجز"""
    try:
        booking = OnlineBooking.query.get_or_404(booking_id)
        return render_template('booking/confirmation.html', booking=booking)
    except Exception as e:
        logging.error(f"Error loading booking confirmation: {str(e)}")
        flash('حدث خطأ في تحميل تأكيد الحجز', 'error')
        return redirect(url_for('booking.index'))

@booking_bp.route('/booking/payment/<int:booking_id>', methods=['GET', 'POST'])
def payment(booking_id):
    """دفع رسوم الحجز"""
    booking = OnlineBooking.query.get_or_404(booking_id)
    
    if request.method == 'POST':
        try:
            # إنشاء معاملة دفع
            payment = PaymentTransaction(
                booking_id=booking_id,
                amount=request.form.get('amount', 50.0),
                payment_method=request.form.get('payment_method'),
                status='pending'
            )
            
            db.session.add(payment)
            db.session.commit()
            
            flash('تم إنشاء معاملة الدفع بنجاح', 'success')
            return redirect(url_for('booking.confirmation', booking_id=booking_id))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error processing payment: {str(e)}")
            flash(f'حدث خطأ في معالجة الدفع: {str(e)}', 'error')
    
    return render_template('booking/payment.html', booking=booking)

@booking_bp.route('/api/available-doctors')
def api_available_doctors():
    """API لجلب الأطباء المتاحين"""
    try:
        department_id = request.args.get('department_id')
        
        if department_id:
            doctors = User.query.filter_by(
                role='doctor', 
                department_id=department_id,
                is_active=True
            ).all()
        else:
            doctors = User.query.filter_by(role='doctor', is_active=True).all()
        
        return jsonify({
            'success': True,
            'doctors': [{'id': doctor.id, 'full_name': doctor.full_name} for doctor in doctors]
        })
        
    except Exception as e:
        logging.error(f"Error getting available doctors: {str(e)}")
        return jsonify({'success': False, 'message': f'حدث خطأ: {str(e)}'})

@booking_bp.route('/api/available-times')
def api_available_times():
    """API لجلب الأوقات المتاحة"""
    try:
        doctor_id = request.args.get('doctor_id')
        date = request.args.get('date')
        
        if not doctor_id or not date:
            return jsonify({'success': False, 'message': 'معاملات مطلوبة'}), 400
        
        # جلب المواعيد الموجودة للطبيب في التاريخ المحدد
        existing_appointments = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == datetime.strptime(date, '%Y-%m-%d').date()
        ).all()
        
        # الأوقات المتاحة (9 صباحاً إلى 5 مساءً)
        available_times = []
        for hour in range(9, 17):
            time_str = f"{hour:02d}:00"
            if not any(apt.appointment_time.strftime('%H:%M') == time_str for apt in existing_appointments):
                available_times.append(time_str)
        
        return jsonify({
            'success': True,
            'available_times': available_times
        })
        
    except Exception as e:
        logging.error(f"Error getting available times: {str(e)}")
        return jsonify({'success': False, 'message': f'حدث خطأ: {str(e)}'})
