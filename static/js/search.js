function showLoadingAnimation() {
    const loadingAnimation = document.getElementById("loading-animation");
    if(loadingAnimation) loadingAnimation.style.display = "block";
    // setTimeout(showScrollingMessages, 5000);
}

function addTorrent(link) {
    fetch("/add_torrent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ link: link }),
    })
        .then((response) => response.json())
        .then((data) => {
            alert(data.message);
            //   hideLoadingSpinner();
        });
}
