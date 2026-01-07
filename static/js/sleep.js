// Enable/disable reason based on quality
document.getElementById("sleepQuality").addEventListener("change", function () {
    const reason = document.getElementById("sleepReason");
    if (this.value === "Good") {
        reason.value = "";
        reason.disabled = true;
    } else {
        reason.disabled = false;
    }
});

let lastSavedSleepData = null; // store data for chatbot

function saveSleep() {
    const hours = document.getElementById("sleepHours").value;
    const quality = document.getElementById("sleepQuality").value;
    const reason = document.getElementById("sleepReason").value;
    const msg = document.getElementById("sleepMsg");

    // Validation
    if (!hours) {
        msg.style.color = "red";
        msg.innerText = "Please select sleep hours.";
        return;
    }
    if (!quality) {
        msg.style.color = "red";
        msg.innerText = "Please select sleep quality.";
        return;
    }
    if ((quality === "Poor" || quality === "Average") && !reason) {
        msg.style.color = "red";
        msg.innerText = "Please select reason for poor sleep.";
        return;
    }

    // Prepare data object matching backend expectation
    const sleepData = {
        hours: Number(hours),
        quality: quality,
        reason: quality === "Good" ? "" : reason
    };

    fetch("/save-health-data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            category: "sleep",
            value: sleepData // send as "value" so backend suggestion works
        })
    })
    .then(res => res.json())
    .then(data => {
        // Save last saved data for chatbot
        lastSavedSleepData = sleepData;

        // Show suggestion from backend
        msg.style.color = "green";
        msg.innerText = data.suggestion || "Sleep data saved successfully.";
    })
    .catch(err => {
        msg.style.color = "red";
        msg.innerText = "Error saving sleep data.";
        console.error(err);
    });
}

// Chatbot button: copy + redirect
function copySleepForChatbot() {
    const msg = document.getElementById("sleepMsg");

    if (!lastSavedSleepData) {
        msg.style.color = "red";
        msg.innerText = "Please save sleep data first.";
        return;
    }

    const text = `Here is my sleep data, please provide guidance:
Sleep Hours: ${lastSavedSleepData.hours}
Sleep Quality: ${lastSavedSleepData.quality}
Reason: ${lastSavedSleepData.reason || "None"}`;

    // Copy to clipboard
    navigator.clipboard.writeText(text).then(() => {
        alert("Your sleep data is copied.\n\n" +
             "Just paste (Ctrl + V) it into the chatbot to get personalized advice.")
        // Redirect to chatbot page
        window.location.href = "/chatbot"; 
    });
}
