function updateClock() {
        const now = new Date();
        const optionsDate = { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric', calendar: 'islamic-umalqura' }; // Islamic date if supported or locale default
        const dateStr = now.toLocaleDateString('ar-SA', optionsDate);
        const timeStr = now.toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        
        document.getElementById('currentDate').textContent = dateStr;
        document.getElementById('currentTime').textContent = timeStr;
    }
    
    // Update every second
    setInterval(updateClock, 1000);
    updateClock(); // Initial call
