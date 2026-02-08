#!/usr/bin/env node

/**
 * Alert Service
 * Checks for pending alerts and sends via Telegram
 */

const fs = require('fs');
const path = require('path');
const sqlite3 = require('sqlite3').verbose();
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

const CONFIG_FILE = path.join(__dirname, 'config.json');
const DB_FILE = path.join(__dirname, 'token-costs.db');
const STATE_FILE = path.join(__dirname, 'alert-state.json');

let config;
try {
    config = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
} catch (error) {
    console.error('❌ Failed to load config:', error.message);
    process.exit(1);
}

// Load alert state (last sent timestamps to enforce cooldown)
let alertState = { lastSent: {} };
if (fs.existsSync(STATE_FILE)) {
    try {
        alertState = JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'));
    } catch (e) {
        console.log('⚠️  Could not load alert state, starting fresh');
    }
}

function saveAlertState() {
    fs.writeFileSync(STATE_FILE, JSON.stringify(alertState, null, 2));
}

async function sendTelegramAlert(alert) {
    if (!config.alerts.telegram.enabled) {
        console.log('📵 Telegram alerts disabled');
        return false;
    }
    
    const userId = config.alerts.telegram.user_id;
    
    // Format message with emoji based on severity
    const emoji = {
        info: 'ℹ️',
        warning: '⚠️',
        critical: '🚨'
    }[alert.severity] || 'ℹ️';
    
    let message = `${emoji} **Token Cost Alert**\n\n`;
    message += `**${alert.message}**\n\n`;
    
    // Parse details if available
    if (alert.details) {
        try {
            const details = JSON.parse(alert.details);
            if (details.period) {
                message += `Period: ${details.period}\n`;
                message += `Spent: $${details.spent.toFixed(2)}\n`;
                message += `Limit: $${details.limit.toFixed(2)}\n`;
                message += `Usage: ${details.percentage.toFixed(1)}%\n`;
            }
        } catch (e) {
            // Details not JSON, just append
            message += `Details: ${alert.details}\n`;
        }
    }
    
    message += `\nTime: ${new Date(alert.timestamp).toLocaleString()}`;
    
    try {
        // Use OpenClaw message tool to send Telegram message
        // We'll create a simple Node script that interfaces with OpenClaw CLI
        const cmd = `/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw message send --target ${userId} --message ${JSON.stringify(message)} --channel telegram`;
        
        await execPromise(cmd);
        console.log(`✅ Sent Telegram alert: ${alert.message}`);
        return true;
        
    } catch (error) {
        console.error('❌ Failed to send Telegram alert:', error.message);
        return false;
    }
}

async function processAlerts() {
    return new Promise((resolve, reject) => {
        const db = new sqlite3.Database(DB_FILE, (err) => {
            if (err) return reject(err);
            
            // Get unsent alerts
            db.all(`
                SELECT * FROM alerts 
                WHERE sent = 0 
                ORDER BY timestamp ASC
                LIMIT 10
            `, async (err, alerts) => {
                if (err) return reject(err);
                
                if (alerts.length === 0) {
                    console.log('✅ No pending alerts');
                    db.close();
                    return resolve();
                }
                
                console.log(`📬 Processing ${alerts.length} pending alert(s)...`);
                
                for (const alert of alerts) {
                    // Check cooldown
                    const cooldownKey = `${alert.type}_${alert.severity}`;
                    const lastSent = alertState.lastSent[cooldownKey] || 0;
                    const cooldownMs = config.alerts.cooldown_minutes * 60 * 1000;
                    
                    if (Date.now() - lastSent < cooldownMs) {
                        console.log(`⏳ Alert in cooldown: ${alert.message}`);
                        continue;
                    }
                    
                    // Send alert
                    const sent = await sendTelegramAlert(alert);
                    
                    if (sent) {
                        // Mark as sent
                        db.run('UPDATE alerts SET sent = 1 WHERE id = ?', [alert.id]);
                        alertState.lastSent[cooldownKey] = Date.now();
                        saveAlertState();
                    }
                }
                
                db.close((err) => {
                    if (err) console.error('Error closing DB:', err.message);
                    resolve();
                });
            });
        });
    });
}

async function main() {
    try {
        console.log('🔔 Alert Service Starting...');
        await processAlerts();
        console.log('✅ Alert service complete');
    } catch (error) {
        console.error('❌ Error:', error.message);
        process.exit(1);
    }
}

main();
