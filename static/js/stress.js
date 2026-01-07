// ---------------- TOGGLE REASON ----------------
function toggleStressReason() {
    const level = document.getElementById("stressLevel").value;
    const reason = document.getElementById("stressReason");

    if (level === "Low") {
        reason.value = "";
        reason.disabled = true;
    } else {
        reason.disabled = false;
    }
}

// ---------------- STORE LAST DATA ----------------
let lastSavedStressData = null;

// ---------------- SAVE STRESS DATA ----------------
function saveStress() {
    const level = document.getElementById("stressLevel").value;
    const reason = document.getElementById("stressReason").value;
    const msg = document.getElementById("stressMsg");

    // Validation
    if (!level) {
        msg.style.color = "red";
        msg.innerText = "Please select stress level.";
        return;
    }

    if ((level === "Medium" || level === "High") && !reason) {
        msg.style.color = "red";
        msg.innerText = "Please select reason for stress.";
        return;
    }

    const stressData = {
        level: level,
        reason: level === "Low" ? "" : reason
    };

    fetch("/save-health-data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            category: "stress",
            value: stressData
        })
    })
    .then(res => res.json())
    .then(data => {
        lastSavedStressData = stressData;

        msg.style.color = "green";
        msg.innerText = data.suggestion || "Stress data saved successfully.";
    })
    .catch(err => {
        msg.style.color = "red";
        msg.innerText = "Error saving stress data.";
        console.error(err);
    });
}

// ---------------- CHATBOT COPY + REDIRECT ----------------
function copyStressForChatbot() {
    const msg = document.getElementById("stressMsg");

    if (!lastSavedStressData) {
        msg.style.color = "red";
        msg.innerText = "Please save stress data first.";
        return;
    }

    const text = `Here is my stress data, please provide guidance:
Stress Level: ${lastSavedStressData.level}
Reason: ${lastSavedStressData.reason || "None"}`;

    navigator.clipboard.writeText(text).then(() => {
        alert("Your stress data is copied.\n\n" +
             "Just paste (Ctrl + V) it into the chatbot to get personalized advice.")
        window.location.href = "/chatbot";
    });
}
