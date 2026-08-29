function updateClock() {
        const now = new Date();
        const optionsDate = { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric', calendar: 'islamic-umalqura' };
        const dateStr = now.toLocaleDateString('ar-SA', optionsDate);
        const timeStr = now.toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        
        const currentDateEl = document.getElementById('currentDate');
        if (currentDateEl) currentDateEl.textContent = dateStr;
        const currentTimeEl = document.getElementById('currentTime');
        if (currentTimeEl) currentTimeEl.textContent = timeStr;
    }
    
    setInterval(updateClock, 1000);
    updateClock();
