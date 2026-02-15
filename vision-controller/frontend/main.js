/**
 * Vision Controller - Electron Main Process
 *
 * Creates the application window and handles system integration.
 *
 * Features:
 * - Creates 800x600 window with camera permissions enabled
 * - Loads index.html for the UI
 * - System tray with context menu
 * - Detection status in tray tooltip
 * - Click tray to toggle window visibility
 */

const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain } = require('electron');
const path = require('path');

// Global references to prevent garbage collection
let mainWindow = null;
let tray = null;

// Detection state
let isDetectionActive = false;
let lastGesture = 'None';

/**
 * Create a simple tray icon using nativeImage.
 * Creates a 16x16 colored square that changes based on detection state.
 */
function createTrayIcon(isActive = false) {
  const size = 16;
  const color = isActive ? '#34C759' : '#FF9500'; // Green for active, orange for paused
  
  // Create a simple colored circle icon
  const svg = `
    <svg width="${size}" height="${size}" xmlns="http://www.w3.org/2000/svg">
      <rect width="${size}" height="${size}" rx="4" fill="${color}"/>
      <circle cx="8" cy="8" r="5" fill="white"/>
      <circle cx="8" cy="8" r="3" fill="${isActive ? '#34C759' : '#FF9500'}"/>
    </svg>
  `;
  
  return nativeImage.createFromBuffer(Buffer.from(svg));
}

/**
 * Get tooltip text based on current state.
 */
function getTooltipText() {
  const status = isDetectionActive ? '● Active' : '○ Paused';
  return `Vision Controller\n${status}\nLast: ${lastGesture}`;
}

/**
 * Update the tray icon and tooltip based on current state.
 */
function updateTray() {
  if (!tray) return;
  
  tray.setImage(createTrayIcon(isDetectionActive));
  tray.setToolTip(getTooltipText());
  
  // Also update context menu to reflect current state
  updateContextMenu();
}

/**
 * Toggle detection on/off.
 */
function toggleDetection() {
  isDetectionActive = !isDetectionActive;
  console.log(`[Electron] Detection ${isDetectionActive ? 'activated' : 'paused'}`);
  updateTray();
  
  // Notify renderer if window exists
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('detection-state-changed', isDetectionActive);
  }
}

/**
 * Update the last detected gesture.
 */
function updateLastGesture(gesture) {
  lastGesture = gesture || 'None';
  console.log(`[Electron] Last gesture: ${lastGesture}`);
  updateTray();
}

/**
 * Toggle main window visibility.
 */
function toggleWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    createWindow();
    return;
  }
  
  if (mainWindow.isVisible()) {
    mainWindow.hide();
    console.log('[Electron] Window hidden');
  } else {
    mainWindow.show();
    mainWindow.focus();
    console.log('[Electron] Window shown');
  }
}

/**
 * Create the system tray icon and context menu.
 */
function createTray() {
  console.log('[Electron] Creating system tray...');
  
  // Create tray icon
  const icon = createTrayIcon(isDetectionActive);
  tray = new Tray(icon);
  
  // Set tooltip
  tray.setToolTip(getTooltipText());
  
  // Create context menu
  updateContextMenu();
  
  // Click handler - toggle window visibility
  tray.on('click', () => {
    console.log('[Electron] Tray clicked - toggling window');
    toggleWindow();
  });
  
  // Right-click shows context menu (macOS/Linux)
  tray.on('right-click', () => {
    tray.popUpContextMenu();
  });
  
  console.log('[Electron] System tray created');
}

/**
 * Update the context menu with current state.
 */
function updateContextMenu() {
  if (!tray) return;
  
  const contextMenu = Menu.buildFromTemplate([
    {
      label: isDetectionActive ? '⏸ Pause Detection' : '▶️ Resume Detection',
      click: toggleDetection,
      accelerator: 'CommandOrControl+D'
    },
    { type: 'separator' },
    {
      label: `Last Gesture: ${lastGesture}`,
      enabled: false
    },
    { type: 'separator' },
    {
      label: '🎛 Settings',
      click: () => {
        console.log('[Electron] Settings clicked');
        // Show main window and focus settings
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.show();
          mainWindow.focus();
          mainWindow.webContents.send('navigate-to', 'settings');
        } else {
          createWindow();
        }
      }
    },
    { type: 'separator' },
    {
      label: '🚪 Quit',
      role: 'quit',
      accelerator: 'CommandOrControl+Q'
    }
  ]);
  
  tray.setContextMenu(contextMenu);
}

/**
 * Create the main application window.
 */
function createWindow() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.show();
    mainWindow.focus();
    return mainWindow;
  }
  
  console.log('[Electron] Creating main window...');
  
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    title: 'Vision Controller',
    webPreferences: {
      // Enable Node.js integration in renderer process
      nodeIntegration: true,
      // Disable context isolation for simpler access
      contextIsolation: false,
      // Allow camera access
      permissions: ['media']
    }
  });

  // Load the UI
  mainWindow.loadFile('index.html');
  
  // Open DevTools for development
  mainWindow.webContents.openDevTools();
  
  // Handle window closed
  mainWindow.on('closed', () => {
    console.log('[Electron] Main window closed');
    mainWindow = null;
  });
  
  // Hide window instead of closing on macOS (optional - keep app running in tray)
  mainWindow.on('close', (event) => {
    if (process.platform === 'darwin' && tray) {
      // On macOS with tray, hide instead of close
      if (!app.isQuiting) {
        event.preventDefault();
        mainWindow.hide();
        console.log('[Electron] Window hidden (tray mode)');
      }
    }
  });
  
  console.log('[Electron] Main window created');
  return mainWindow;
}

// App ready - create window and tray
app.whenReady().then(() => {
  console.log('[Electron] Application ready');
  
  // Create main window
  createWindow();
  
  // Create system tray
  createTray();
  
  // IPC handlers for renderer communication
  ipcMain.on('gesture-detected', (event, gesture) => {
    updateLastGesture(gesture);
  });
  
  ipcMain.on('set-detection-state', (event, active) => {
    isDetectionActive = active;
    updateTray();
  });
  
  // On macOS, recreate window when dock icon clicked
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// All windows closed
app.on('window-all-closed', () => {
  console.log('[Electron] All windows closed');
  
  // If tray is active, keep app running
  if (tray) {
    console.log('[Electron] Tray active - keeping app alive');
    return;
  }
  
  // On Windows/Linux, quit the app
  // On macOS, apps typically stay alive until Cmd+Q
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// App about to quit
app.on('will-quit', () => {
  console.log('[Electron] Application quitting...');
  
  // Destroy tray to prevent orphaned icons
  if (tray) {
    tray.destroy();
    tray = null;
  }
});

// Handle Cmd+W on macOS to hide window when in tray mode
app.on('before-quit', () => {
  app.isQuiting = true;
});

// Export for potential testing
module.exports = { createTrayIcon, getTooltipText };
