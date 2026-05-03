let eventSource = null;

function showLoadingAnimation() {
    document.getElementById('results-table-body').innerHTML = '';
    const loadingAnimation = document.getElementById("loading-animation");
    if (loadingAnimation) loadingAnimation.style.display = "block";
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


function startSearch() {
    hideError();
    const query = document.querySelector('[name=query]').value;
    const baseUrl = document.querySelector('[name=base_url]').value;
    const titleOnly = document.querySelector('[name=title_only]').checked;
    const scraper = document.querySelector('[name=scraper]').value;


    // clear previous results
    document.getElementById('results-table-body').innerHTML = '';
    showLoadingAnimation();

    // close any existing stream
    if (eventSource) eventSource.close();

    const params = new URLSearchParams({
        query,
        base_url: baseUrl,
        title_only: titleOnly ? "1" : "0",
        scraper: scraper
    });

    eventSource = new EventSource(`/search/stream?${params}`);

    eventSource.onmessage = (event) => {
        if (event.data === "DONE") {
            eventSource.close();
            hideLoadingAnimation();
            return;
        }
        const data = JSON.parse(event.data);
        if (data.error) {
            showError(data.error);
            return;
        }
        appendBook(data);
    };

    eventSource.onerror = () => {
        eventSource.close();
        hideLoadingAnimation();
    };
}

function appendBook(book) {
    const tbody = document.getElementById('results-table-body');
    const row = document.createElement('tr');
    row.className = 'result-row';
    row.innerHTML = `
        <td><img src="${book.Poster}" alt="Cover Art" class="cover" width="100"></td>
        <td>
            <div class="property-results-container">
                <span class="book-title"><a href="${book.Details}">${book.Title}</a></span>
            </div>
        </td>
        <td><button onclick="addTorrent('${book.Link}')">Add</button></td>
    `;
    tbody.appendChild(row);
}

function showError(message) {
    // reuse your existing error box
    const box = document.getElementById('error-box');
    if (box) {
        box.textContent = message;
        box.style.display = 'block';
    }
}
function hideError() {
    const box = document.getElementById('error-box');
    if (box) {
        box.style.display = 'none';
    }
}

function hideLoadingAnimation() {
    document.getElementById('loading-animation').style.display = 'none';
    document.getElementById('button-spinner').style.display = 'none';
    document.querySelector('.button-text').style.display = 'inline';
}