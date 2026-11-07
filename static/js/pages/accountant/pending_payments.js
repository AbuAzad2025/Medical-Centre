export function refreshPage() {
    location.reload();
}

setInterval(function() {

}, 60000);


// Backward compatibility
if (typeof refreshPage !== "undefined") window.refreshPage = refreshPage;
