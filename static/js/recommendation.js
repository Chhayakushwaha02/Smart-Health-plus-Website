function loadRecommendations() {
    fetch("/generate-recommendation")
        .then(res => res.json())
        .then(data => {

            document.getElementById("recommendationBox").innerHTML =
                `<p>${data.recommendation}</p>`;

            document.getElementById("healthSummaryText").innerText =
                data.health_summary;

            document.getElementById("healthSummaryBox").style.display = "block";
        })
        .catch(err => {
            console.error(err);
            alert("Failed to generate recommendations");
        });
}
