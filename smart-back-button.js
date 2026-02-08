/**
 * Smart Back Button - Finds existing Command Hub tab or opens new one
 * Add this script to dashboards and call navigateToHub()
 */

function navigateToHub(event) {
    if (event) event.preventDefault();
    
    const hubUrl = 'http://localhost:18795/hub';
    
    // Try to find existing Command Hub tab
    if (window.opener && !window.opener.closed) {
        // We were opened by another window, check if it's the hub
        try {
            if (window.opener.location.href.includes('localhost:18795')) {
                window.opener.focus();
                return;
            }
        } catch (e) {
            // Cross-origin, can't check
        }
    }
    
    // Fallback: Try to use existing named window or open new one
    const hubWindow = window.open(hubUrl, 'command-hub');
    if (hubWindow) {
        hubWindow.focus();
    }
}
