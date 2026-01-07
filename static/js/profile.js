let data = `
<li>Sleep: ${localStorage.getItem("sleep")}</li>
<li>Stress: ${localStorage.getItem("stress")}</li>
<li>Mood: ${localStorage.getItem("mood")}</li>
<li>Water: ${localStorage.getItem("water")} glasses</li>
<li>Nutrition: ${localStorage.getItem("nutrition")}</li>
<li>Fitness: ${localStorage.getItem("fitness")} steps</li>
`;

document.getElementById("profileData").innerHTML = data;
