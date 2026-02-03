// Tracks whether a Pull Data request is currently in progress.
// Used to prevent Update Analysis from reloading during a scrape.
var isPulling = false;

// Sends a POST request to /pull-data to scrape new entries from
// thegradcafe.com and insert them into the database.
function pullData() {
    var btn = document.getElementById("pull-btn");
    var status = document.getElementById("pull-status");
    var pages = parseInt(document.getElementById("pages").value) || 5;

    // Disable both buttons while scraping
    isPulling = true;
    btn.disabled = true;
    btn.textContent = "Pulling\u2026";
    document.getElementById("update-btn").disabled = true;

    // Show in-progress status message
    status.className = "pull-data-status info";
    status.style.display = "block";
    status.textContent = "Scraping " + pages + " page(s) from thegradcafe.com\u2026 this may take a moment.";

    fetch("/pull-data", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({pages: pages})
    })
    .then(function(res) { return res.json().then(function(data) { return {ok: res.ok, data: data}; }); })
    .then(function(result) {
        isPulling = false;

        // Show success or error status
        if (!result.ok) {
            status.className = "pull-data-status error";
            status.textContent = result.data.error || "Request failed.";
        } else {
            status.className = "pull-data-status success";
            status.textContent = result.data.message;
        }

        // Re-enable both buttons
        btn.disabled = false;
        btn.textContent = "Pull Data";
        document.getElementById("update-btn").disabled = false;
    })
    .catch(function(err) {
        isPulling = false;

        // Show network error
        status.className = "pull-data-status error";
        status.textContent = "Network error: " + err.message;

        // Re-enable both buttons
        btn.disabled = false;
        btn.textContent = "Pull Data";
        document.getElementById("update-btn").disabled = false;
    });
}

// Reloads the page to refresh analysis results with current database contents.
// Does nothing if a Pull Data request is still running.
function updateAnalysis() {
    var uaStatus = document.getElementById("ua-status");
    if (isPulling) {
        uaStatus.className = "ua-status warn";
        uaStatus.textContent = "A Pull Data request is still running. Please wait for it to finish.";
        return;
    }
    location.reload();
}