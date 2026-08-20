let eventSource = null;

function showLoadingAnimation() {
    document.getElementById('results-table-body').innerHTML = '';
    const loadingAnimation = document.getElementById("loading-animation");
    if (loadingAnimation) loadingAnimation.style.display = "block";
    // setTimeout(showScrollingMessages, 5000);
}

function addTorrent(link, source, book_title, btn) {
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner" style="width:14px;height:14px;border-width:2px;margin:0 auto;"></div>';

    fetch("/add_torrent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ link: link, source: source, book_title: book_title }),
    })
        .then((response) => response.json())
        .then((data) => {
            btn.innerHTML = "✓";
            btn.style.opacity = "0.6";
            btn.style.backgroundColor = "#227e26";

        })
        .catch(() => {
            btn.innerHTML = "Error";
            btn.style.backgroundColor = "#dc3545";
            btn.disabled = false;
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

    const badges = [book.Language, book.Format, book.Bitrate, book.fileSize]
        .filter(Boolean)
        .map(v => `<span class="book-badge">${v}</span>`)
        .join('');

    const poster = book.Poster
        ? `<img src="${book.Poster}" alt="Cover Art" class="cover">`
        : `<div class="cover-placeholder">No cover</div>`;

    row.innerHTML = `
        <td>${poster}</td>
        <td>
            <a class="book-title" href="${book.Details}">${book.Title}</a>
            <div class="book-badges">${badges}</div>
            ${book.Date ? `<span class="book-date">${book.Date}</span>` : ''}
        </td>
        <td><button class="card-add-button" onclick="addTorrent('${book.Link}', '${book.Source}', '${book.Title}', this)">Add</button></td>
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