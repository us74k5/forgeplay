
document.getElementById('playButton').addEventListener('click', () => {
    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
        chrome.scripting.executeScript({
            target: { tabId: tabs[0].id },
            function: playVideoLocally
        });
    });
});

function playVideoLocally() {
    fetch('http://localhost:8000/get_video_url')
        .then(response => response.json())
        .then(data => {
            const video = document.createElement('video');
            video.src = data.url;
            video.controls = true;
            video.autoplay = true;
            document.body.appendChild(video);
        });
}
