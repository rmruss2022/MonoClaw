/**
 * Smart Hub Navigation
 * Finds existing Command Hub tab in current window or opens new one
 * Uses BroadcastChannel API to communicate between tabs
 */

const HUB_URL = 'http://localhost:18795/hub';
const HUB_CHANNEL = 'openclaw-hub-channel';

function navigateToHub(event) {
    // Prevent default link behavior
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    
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
            // Hub is open and will focus itself - we do nothing
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
    
    return false; // Extra safety to prevent default
}

// If this page IS the hub, respond to pings
if (window.location.href.includes('localhost:18795')) {
    const bc = new BroadcastChannel(HUB_CHANNEL);
    bc.onmessage = (e) => {
        if (e.data.type === 'hub-ping') {
            // We are the hub! Send confirmation
            bc.postMessage({ type: 'hub-present' });
            // Try to focus ourselves (without reload)
            try {
                if (document.hidden || !document.hasFocus()) {
                    window.focus();
                }
            } catch (err) {
                // Focus might fail in some browsers, that's okay
                console.log('Could not focus hub tab');
            }
        }
    };
}
