// Enable / disable reason based on hydration level
function toggleHydrationReason() {
    const level = document.getElementById("hydrationLevel").value;
    const reason = document.getElementById("hydrationReason");

    if (level === "High") {
        reason.value = "";
        reason.disabled = true;
    } else {
        reason.disabled = false;
    }
}

let lastSavedHydrationData = null; // store data for chatbot

function saveHydration() {
    const level = document.getElementById("hydrationLevel").value;
    const reason = document.getElementById("hydrationReason").value;
    const msg = document.getElementById("hydrationMsg");

    // Validation (ONLY on Save)
    if (!level) {
        msg.style.color = "red";
        msg.innerText = "Please select water intake level.";
        return;
    }

    if ((level === "Low" || level === "Moderate") && !reason) {
        msg.style.color = "red";
        msg.innerText = "Please select reason for low/moderate hydration.";
        return;
    }

    // Backend-compatible structure
    const hydrationData = {
        level: level,
        reason: level === "High" ? "" : reason
    };

    fetch("/save-health-data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            category: "hydration",
            value: hydrationData
        })
    })
    .then(res => res.json())
    .then(data => {
        lastSavedHydrationData = hydrationData;

        msg.style.color = "green";
        msg.innerText =
            data.suggestion ||
            "Hydration data saved successfully.\n\nFor more personalized guidance, click the chatbot button above.";
    })
    .catch(err => {
        msg.style.color = "red";
        msg.innerText = "Error saving hydration data.";
        console.error(err);
    });
}

// Chatbot button: copy + redirect (same pattern as sleep)
function copyHydrationForChatbot() {
    const msg = document.getElementById("hydrationMsg");

    if (!lastSavedHydrationData) {
        msg.style.color = "red";
        msg.innerText = "Please save hydration data first.";
        return;
    }

    const text = `Here is my hydration data, please provide guidance:
Water Intake Level: ${lastSavedHydrationData.level}
Reason: ${lastSavedHydrationData.reason || "None"}`;

    navigator.clipboard.writeText(text).then(() => {
        alert("Your hydration data is copied.\n\n" +
             "Just paste (Ctrl + V) it into the chatbot to get personalized advice.")
        window.location.href = "/chatbot";
    });
}
