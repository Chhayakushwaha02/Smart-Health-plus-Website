// ---------------- TOGGLE REASON ----------------
function toggleMoodReason() {
    const mood = document.getElementById("moodValue").value;
    const reason = document.getElementById("moodReason");

    if (mood === "Sad" || mood === "Angry") {
        reason.disabled = false;
    } else {
        reason.value = "";
        reason.disabled = true;
    }
}

// ---------------- STORE LAST DATA ----------------
let lastSavedMoodData = null;

// ---------------- SAVE MOOD DATA ----------------
function saveMood() {
    const mood = document.getElementById("moodValue").value;
    const reason = document.getElementById("moodReason").value;
    const msg = document.getElementById("moodMsg");

    // Validation
    if (!mood) {
        msg.style.color = "red";
        msg.innerText = "Please select your mood.";
        return;
    }

    if ((mood === "Sad" || mood === "Angry") && !reason) {
        msg.style.color = "red";
        msg.innerText = "Please select reason for your mood.";
        return;
    }

    const moodData = {
        mood: mood,
        reason: (mood === "Sad" || mood === "Angry") ? reason : ""
    };

    fetch("/save-health-data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            category: "mood",
            value: moodData
        })
    })
    .then(res => res.json())
    .then(data => {
        lastSavedMoodData = moodData;

        msg.style.color = "green";
        msg.innerText = data.suggestion || "Mood data saved successfully.";
    })
    .catch(err => {
        msg.style.color = "red";
        msg.innerText = "Error saving mood data.";
        console.error(err);
    });
}

// ---------------- CHATBOT COPY + REDIRECT ----------------
function copyMoodForChatbot() {
    const msg = document.getElementById("moodMsg");

    if (!lastSavedMoodData) {
        msg.style.color = "red";
        msg.innerText = "Please save mood data first.";
        return;
    }

    const text = `Here is my mood data, please provide guidance:
Mood: ${lastSavedMoodData.mood}
Reason: ${lastSavedMoodData.reason || "None"}`;

    navigator.clipboard.writeText(text).then(() => {
        alert("Your mood data is copied.\n\n" +
             "Just paste (Ctrl + V) it into the chatbot to get personalized advice.")
        window.location.href = "/chatbot";
    });
}
