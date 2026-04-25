
document.getElementById('enableNavigationHandling').addEventListener('change', (event) => {
  const isEnabled = event.target.checked;
  chrome.storage.sync.set({ navigationEnabled: isEnabled }, () => {
    console.log(`Navigation handling is now ${isEnabled ? 'enabled' : 'disabled'}`);
  });
});

chrome.storage.sync.get(['navigationEnabled'], (result) => {
  if (result.navigationEnabled !== undefined) {
    document.getElementById('enableNavigationHandling').checked = result.navigationEnabled;
  }
});
