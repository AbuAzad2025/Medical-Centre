export function refreshPage() {
    location.reload();
}

// Backward compatibility
if (typeof refreshPage !== "undefined") window.refreshPage = refreshPage;
