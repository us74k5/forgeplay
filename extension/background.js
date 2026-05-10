const HELPER_DOWNLOAD_URL = "http://127.0.0.1:8000/download";

function getSettings(keys) {
    return new Promise((resolve) => {
        chrome.storage.sync.get(keys, resolve);
    });
}

function createPlaybackTab(url) {
    return new Promise((resolve, reject) => {
        chrome.tabs.create({ url, active: true }, (tab) => {
            const error = chrome.runtime.lastError;
            if (error) {
                reject(new Error(error.message));
                return;
            }
            resolve(tab);
        });
    });
}

async function requestHelperPlayback(videoUrl, quality) {
    const response = await fetch(HELPER_DOWNLOAD_URL, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            url: videoUrl,
            quality,
        }),
    });

    let data = {};
    try {
        data = await response.json();
    } catch (error) {
        throw new Error(`Helper returned non-JSON response (${response.status})`);
    }

    if (!response.ok) {
        throw new Error(data.detail || `Helper returned ${response.status}`);
    }

    if (!data.playerUrl) {
        throw new Error("Helper response did not include a player URL");
    }

    return data.playerUrl;
}

async function handleCaptureUrl(request) {
    const settings = await getSettings(["quality"]);
    const quality = settings.quality || "720";

    console.info("ForgePlay sending URL to helper", {
        url: request.url,
        quality,
    });

    const playerUrl = await requestHelperPlayback(request.url, quality);
    await createPlaybackTab(playerUrl);

    return {
        success: true,
        playerUrl,
    };
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (!request || request.action !== "captureUrl") {
        return false;
    }

    handleCaptureUrl(request)
        .then(sendResponse)
        .catch((error) => {
            console.error("ForgePlay helper request failed", error);
            sendResponse({
                success: false,
                error: String(error && error.message ? error.message : error),
            });
        });

    return true;
});
