// ---------------- ENABLE / DISABLE REASON ----------------
function toggleNutritionReason() {
    const quality = document.getElementById("nutritionQuality").value;
    const reason = document.getElementById("nutritionReason");

    if (quality === "Good") {
        reason.value = "";
        reason.disabled = true;
    } else if (quality === "Average" || quality === "Poor") {
        reason.disabled = false;
    } else {
        reason.value = "";
        reason.disabled = true;
    }
}

// ---------------- STORE LAST DATA FOR CHATBOT ----------------
let lastSavedNutritionData = null;

// ---------------- SAVE NUTRITION ----------------
function saveNutrition() {
    const quality = document.getElementById("nutritionQuality").value;
    const reason = document.getElementById("nutritionReason").value;
    const msg = document.getElementById("nutritionMsg");

    // VALIDATION
    if (!quality) {
        msg.style.color = "red";
        msg.innerText = "Please select nutrition quality.";
        return;
    }

    if ((quality === "Average" || quality === "Poor") && !reason) {
        msg.style.color = "red";
        msg.innerText = "Please select a reason.";
        return;
    }

    const nutritionData = {
        quality: quality,
        reason: quality === "Good" ? "" : reason
    };

    fetch("/save-health-data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            category: "nutrition",
            value: nutritionData
        })
    })
    .then(res => res.json())
    .then(data => {
        lastSavedNutritionData = nutritionData;

        msg.style.color = "green";
        msg.innerText = data.suggestion || "Nutrition data saved successfully.";
    })
    .catch(err => {
        msg.style.color = "red";
        msg.innerText = "Error saving nutrition data.";
        console.error(err);
    });
}

// ---------------- CHATBOT COPY + REDIRECT ----------------
function copyNutritionForChatbot() {
    const msg = document.getElementById("nutritionMsg");

    if (!lastSavedNutritionData) {
        msg.style.color = "red";
        msg.innerText = "Please save nutrition data first.";
        return;
    }

    const text = `Here is my nutrition data, please provide guidance:
Nutrition Quality: ${lastSavedNutritionData.quality}
Reason: ${lastSavedNutritionData.reason || "None"}`;

    navigator.clipboard.writeText(text).then(() => {
        alert("Your nutrition data is copied.\n\n" +
             "Just paste (Ctrl + V) it into the chatbot to get personalized advice.")
        window.location.href = "/chatbot";
    });
}
