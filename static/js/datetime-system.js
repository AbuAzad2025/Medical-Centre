/**
 * نظام الوقت والتاريخ الموحد
 * Unified DateTime System
 */

class DateTimeSystem {
    constructor() {
        this.timezone = 'Asia/Gaza';
        this.locale = 'ar-SA';
        this.updateInterval = 1000; // تحديث كل ثانية
        this.isRunning = false;
        this.observers = [];
        this.init();
    }

    init() {
        this.setupDateTimeElements();
        this.startRealTimeUpdates();
        this.setupTimezoneDetection();
        this.setupKeyboardShortcuts();
    }

    // إعداد عناصر الوقت والتاريخ
    setupDateTimeElements() {
        // إنشاء عناصر الوقت والتاريخ إذا لم تكن موجودة
        this.createDateTimeElements();
        
        // ربط العناصر الموجودة
        this.bindExistingElements();
    }

    // إنشاء عناصر جديدة للوقت والتاريخ
    createDateTimeElements() {
        const header = document.querySelector('.header-advanced');
        if (header && !document.querySelector('.datetime-display')) {
            const datetimeContainer = document.createElement('div');
            datetimeContainer.className = 'datetime-display';
            datetimeContainer.innerHTML = `
                <div class="datetime-info">
                    <div class="current-time">
                        <i class="fas fa-clock"></i>
                        <span class="time-text">--:--:--</span>
                    </div>
                    <div class="current-date">
                        <i class="fas fa-calendar"></i>
                        <span class="date-text">--/--/----</span>
                    </div>
                    <div class="timezone-info">
                        <i class="fas fa-globe"></i>
                        <span class="timezone-text">${this.timezone}</span>
                    </div>
                </div>
            `;
            
            // إدراج في الهيدر
            const userSection = header.querySelector('.user-section');
            if (userSection && userSection.parentNode === header) {
                header.insertBefore(datetimeContainer, userSection);
            } else {
                header.appendChild(datetimeContainer);
            }
        }
    }

    // ربط العناصر الموجودة
    bindExistingElements() {
        // البحث عن جميع عناصر الوقت والتاريخ
        this.timeElements = document.querySelectorAll('.current-time, .time-text, [data-datetime="time"]');
        this.dateElements = document.querySelectorAll('.current-date, .date-text, [data-datetime="date"]');
        this.datetimeElements = document.querySelectorAll('.datetime-display, [data-datetime="both"]');
    }

    // بدء التحديث المباشر
    startRealTimeUpdates() {
        if (this.isRunning) return;
        
        this.isRunning = true;
        this.updateDateTime();
        
        this.intervalId = setInterval(() => {
            this.updateDateTime();
        }, this.updateInterval);
    }

    // تحديث الوقت والتاريخ
    updateDateTime() {
        const now = new Date();
        const timeString = this.formatTime(now);
        const dateString = this.formatDate(now);
        const fullDateTime = this.formatFullDateTime(now);

        // تحديث عناصر الوقت
        this.timeElements.forEach(element => {
            if (element.classList.contains('time-text') || element.classList.contains('current-time')) {
                element.textContent = timeString;
            } else {
                element.textContent = timeString;
            }
        });

        // تحديث عناصر التاريخ
        this.dateElements.forEach(element => {
            if (element.classList.contains('date-text') || element.classList.contains('current-date')) {
                element.textContent = dateString;
            } else {
                element.textContent = dateString;
            }
        });

        // تحديث العناصر المختلطة
        this.datetimeElements.forEach(element => {
            const timeSpan = element.querySelector('.time-text');
            const dateSpan = element.querySelector('.date-text');
            
            if (timeSpan) timeSpan.textContent = timeString;
            if (dateSpan) dateSpan.textContent = dateString;
        });

        // إشعار المراقبين
        this.notifyObservers({
            time: timeString,
            date: dateString,
            fullDateTime: fullDateTime,
            timestamp: now.getTime()
        });
    }

    // تنسيق الوقت
    formatTime(date) {
        return date.toLocaleTimeString(this.locale, {
            timeZone: this.timezone,
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }

    // تنسيق التاريخ
    formatDate(date) {
        return date.toLocaleDateString(this.locale, {
            timeZone: this.timezone,
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
    }

    // تنسيق التاريخ والوقت معاً
    formatFullDateTime(date) {
        return date.toLocaleString(this.locale, {
            timeZone: this.timezone,
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
    }

    // إعداد كشف المنطقة الزمنية
    setupTimezoneDetection() {
        // كشف المنطقة الزمنية للمستخدم
        const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        if (userTimezone !== this.timezone) {
            console.log(`User timezone detected: ${userTimezone}`);
            // يمكن تغيير المنطقة الزمنية حسب تفضيل المستخدم
        }
    }

    // إعداد اختصارات لوحة المفاتيح
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl + T لإظهار/إخفاء الوقت
            if (e.ctrlKey && e.key === 't') {
                e.preventDefault();
                this.toggleDateTimeDisplay();
            }
            
            // Ctrl + D لإظهار التاريخ الكامل
            if (e.ctrlKey && e.key === 'd') {
                e.preventDefault();
                this.showFullDateTime();
            }
        });
    }

    // تبديل عرض الوقت والتاريخ
    toggleDateTimeDisplay() {
        const datetimeDisplay = document.querySelector('.datetime-display');
        if (datetimeDisplay) {
            datetimeDisplay.style.display = datetimeDisplay.style.display === 'none' ? 'block' : 'none';
        }
    }

    // إظهار التاريخ والوقت الكامل
    showFullDateTime() {
        const now = new Date();
        const fullDateTime = this.formatFullDateTime(now);
        
        // إنشاء نافذة منبثقة للتاريخ والوقت الكامل
        this.showDateTimeModal(fullDateTime);
    }

    // إظهار نافذة التاريخ والوقت
    showDateTimeModal(fullDateTime) {
        const modal = document.createElement('div');
        modal.className = 'datetime-modal';
        modal.innerHTML = `
            <div class="datetime-modal-content">
                <div class="datetime-modal-header">
                    <h3><i class="fas fa-clock"></i> الوقت والتاريخ الحالي</h3>
                    <button class="close-btn" onclick="this.parentElement.parentElement.parentElement.remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="datetime-modal-body">
                    <div class="datetime-info-full">
                        <div class="datetime-item">
                            <i class="fas fa-clock"></i>
                            <span>الوقت: ${this.formatTime(new Date())}</span>
                        </div>
                        <div class="datetime-item">
                            <i class="fas fa-calendar"></i>
                            <span>التاريخ: ${this.formatDate(new Date())}</span>
                        </div>
                        <div class="datetime-item">
                            <i class="fas fa-globe"></i>
                            <span>المنطقة الزمنية: ${this.timezone}</span>
                        </div>
                        <div class="datetime-item">
                            <i class="fas fa-calendar-alt"></i>
                            <span>التاريخ الكامل: ${fullDateTime}</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // إزالة النافذة بعد 5 ثوان
        setTimeout(() => {
            if (modal.parentElement) {
                modal.remove();
            }
        }, 5000);
    }

    // إضافة مراقب للتحديثات
    addObserver(callback) {
        this.observers.push(callback);
    }

    // إزالة مراقب
    removeObserver(callback) {
        this.observers = this.observers.filter(obs => obs !== callback);
    }

    // إشعار المراقبين
    notifyObservers(data) {
        this.observers.forEach(observer => {
            try {
                observer(data);
            } catch (error) {
                console.error('DateTime observer error:', error);
            }
        });
    }

    // توقف النظام
    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        this.isRunning = false;
    }

    // إعادة تشغيل النظام
    restart() {
        this.stop();
        this.startRealTimeUpdates();
    }

    // تغيير المنطقة الزمنية
    setTimezone(timezone) {
        this.timezone = timezone;
        this.updateDateTime();
    }

    // تغيير اللغة
    setLocale(locale) {
        this.locale = locale;
        this.updateDateTime();
    }

    // الحصول على الوقت الحالي
    getCurrentTime() {
        return new Date();
    }

    // الحصول على التاريخ الحالي
    getCurrentDate() {
        return new Date();
    }

    // تحويل التاريخ إلى نص
    formatDateToString(date, format = 'full') {
        const options = {
            full: {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                weekday: 'long'
            },
            short: {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit'
            },
            time: {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            }
        };

        return date.toLocaleDateString(this.locale, {
            timeZone: this.timezone,
            ...options[format]
        });
    }
}

// إنشاء مثيل عالمي لنظام الوقت والتاريخ
window.dateTimeSystem = new DateTimeSystem();

// إضافة CSS للعناصر
const style = document.createElement('style');
style.textContent = `
    .datetime-display {
        display: flex;
        align-items: center;
        gap: 15px;
        background: rgba(255, 255, 255, 0.1);
        padding: 8px 15px;
        border-radius: 25px;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }

    .datetime-info {
        display: flex;
        align-items: center;
        gap: 15px;
    }

    .current-time, .current-date, .timezone-info {
        display: flex;
        align-items: center;
        gap: 5px;
        color: white;
        font-weight: 500;
        font-size: 0.9rem;
    }

    .time-text, .date-text, .timezone-text {
        font-family: 'Cairo', sans-serif;
        font-weight: 600;
    }

    .datetime-modal {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
    }

    .datetime-modal-content {
        background: white;
        border-radius: 15px;
        padding: 20px;
        max-width: 400px;
        width: 90%;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
    }

    .datetime-modal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
        padding-bottom: 10px;
        border-bottom: 1px solid #eee;
    }

    .datetime-modal-header h3 {
        margin: 0;
        color: #333;
        font-size: 1.2rem;
    }

    .close-btn {
        background: none;
        border: none;
        font-size: 1.2rem;
        cursor: pointer;
        color: #666;
    }

    .datetime-info-full {
        display: flex;
        flex-direction: column;
        gap: 15px;
    }

    .datetime-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px;
        background: #f8f9fa;
        border-radius: 8px;
        font-weight: 500;
    }

    .datetime-item i {
        color: #007bff;
        width: 20px;
    }

    @media (max-width: 768px) {
        .datetime-display {
            flex-direction: column;
            gap: 5px;
            padding: 5px 10px;
        }
        
        .datetime-info {
            flex-direction: column;
            gap: 5px;
        }
        
        .current-time, .current-date, .timezone-info {
            font-size: 0.8rem;
        }
    }
`;
document.head.appendChild(style);

// تصدير النظام للاستخدام العام
window.DateTimeSystem = DateTimeSystem;
