function saveReminder() {
    const type = document.getElementById("reminderType").value;
    const time = document.getElementById("reminderTime").value;
    const email = document.getElementById("email").value;  // grab email from form
    const phone = document.getElementById("phone").value;  // grab phone from form
    const msg = document.getElementById("reminderMsg");

    if (!type || !time || !email || !phone) {
        msg.style.color = "red";
        msg.innerText = "All fields are required";
        return;
    }

    fetch("/save-reminder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, time, email, phone })  // ✅ send all 4 values
    })
    .then(res => res.json())
    .then(data => {
        msg.style.color = "green";
        msg.innerText = data.message;
    })
    .catch(err => {
        msg.style.color = "red";
        msg.innerText = "Error saving reminder";
        console.error(err);
    });
}
