/**
 * Smart Hub Navigation
 * Finds existing Command Hub tab in current window or opens new one
 * Uses BroadcastChannel API to communicate between tabs
 */

const HUB_URL = 'http://localhost:18795/hub';
const HUB_CHANNEL = 'openclaw-hub-channel';

function navigateToHub(event) {
    if (event) event.preventDefault();
    
    // Create a broadcast channel to ask if hub is already open
    const bc = new BroadcastChannel(HUB_CHANNEL);
    let hubFound = false;
    let timeout;
    
    // Listen for response from hub
    bc.onmessage = (e) => {
        if (e.data.type === 'hub-present') {
            hubFound = true;
            clearTimeout(timeout);
            bc.close();
            // Hub is open, it will focus itself
        }
    };
    
    // Ask if hub is open
    bc.postMessage({ type: 'hub-ping' });
    
    // Wait 100ms for response
    timeout = setTimeout(() => {
        bc.close();
        if (!hubFound) {
            // No hub found, open new one
            window.open(HUB_URL, 'command-hub');
        }
    }, 100);
}

// If this page IS the hub, respond to pings
if (window.location.href.includes('localhost:18795')) {
    const bc = new BroadcastChannel(HUB_CHANNEL);
    bc.onmessage = (e) => {
        if (e.data.type === 'hub-ping') {
            // We are the hub! Send confirmation and focus ourselves
            bc.postMessage({ type: 'hub-present' });
            window.focus();
        }
    };
}
