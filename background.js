
import { onMessage } from 'chrome';

onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'handleNavigation') {
    // Handle navigation logic here
    console.log('Handling YouTube SPA navigation');
    sendResponse({ success: true });
  }
});
