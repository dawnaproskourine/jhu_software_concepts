var isPulling = false;

function pullData() {
    var btn = document.getElementById("pull-btn");
    var status = document.getElementById("pull-status");
    var pages = parseInt(document.getElementById("pages").value) || 5;

    isPulling = true;
    btn.disabled = true;
    btn.textContent = "Pulling\u2026";
    document.getElementById("update-btn").disabled = true;
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
        if (!result.ok) {
            status.className = "pull-data-status error";
            status.textContent = result.data.error || "Request failed.";
        } else {
            status.className = "pull-data-status success";
            status.textContent = result.data.message;
        }
        btn.disabled = false;
        btn.textContent = "Pull Data";
        document.getElementById("update-btn").disabled = false;
    })
    .catch(function(err) {
        isPulling = false;
        status.className = "pull-data-status error";
        status.textContent = "Network error: " + err.message;
        btn.disabled = false;
        btn.textContent = "Pull Data";
        document.getElementById("update-btn").disabled = false;
    });
}

function updateAnalysis() {
    var uaStatus = document.getElementById("ua-status");
    if (isPulling) {
        uaStatus.className = "ua-status warn";
        uaStatus.textContent = "A Pull Data request is still running. Please wait for it to finish.";
        return;
    }
    location.reload();
}