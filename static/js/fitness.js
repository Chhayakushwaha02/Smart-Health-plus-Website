// ---------------- STORE LAST DATA FOR CHATBOT ----------------
let lastSavedFitnessData = null;

// ---------------- SAVE FITNESS DATA ----------------
function saveFitness() {
    const minutes = document.getElementById("workoutMinutes").value;
    const type = document.getElementById("workoutType").value;
    const steps = document.getElementById("dailySteps").value;
    const msg = document.getElementById("fitnessMsg");

    // ---------------- VALIDATION ----------------
    if (!minutes && !steps) {
        msg.style.color = "red";
        msg.innerText = "Please enter workout minutes or daily steps.";
        return;
    }

    if (minutes && minutes <= 0) {
        msg.style.color = "red";
        msg.innerText = "Workout minutes must be greater than 0.";
        return;
    }

    if (steps && steps <= 0) {
        msg.style.color = "red";
        msg.innerText = "Daily steps must be greater than 0.";
        return;
    }

    // ---------------- PREPARE DATA ----------------
    const fitnessData = {
        workout_minutes: minutes ? Number(minutes) : 0,
        workout_type: type || "",
        daily_steps: steps ? Number(steps) : 0
    };

    // ---------------- SAVE TO BACKEND ----------------
    fetch("/save-health-data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            category: "fitness",
            value: fitnessData
        })
    })
    .then(res => res.json())
    .then(data => {
        lastSavedFitnessData = fitnessData;

        msg.style.color = "green";
        msg.innerText = data.suggestion || "Fitness data saved successfully.";
    })
    .catch(err => {
        msg.style.color = "red";
        msg.innerText = "Error saving fitness data.";
        console.error(err);
    });
}

// ---------------- CHATBOT COPY + REDIRECT ----------------
function copyFitnessForChatbot() {
    const msg = document.getElementById("fitnessMsg");

    if (!lastSavedFitnessData) {
        msg.style.color = "red";
        msg.innerText = "Please save fitness data first.";
        return;
    }

    const text = `Here is my fitness data, please provide guidance:
Workout Minutes: ${lastSavedFitnessData.workout_minutes || "Not provided"}
Workout Type: ${lastSavedFitnessData.workout_type || "Not specified"}
Daily Steps: ${lastSavedFitnessData.daily_steps || "Not provided"}`;

    navigator.clipboard.writeText(text).then(() => {
        alert("Your fitness data is copied.\n\n" +
             "Just paste (Ctrl + V) it into the chatbot to get personalized advice.")
        window.location.href = "/chatbot";
    });
}
