#!/usr/bin/env node

/**
 * Enhanced Token Cost Collector
 * Parses openclaw status, tracks all sessions, calculates costs, manages budgets
 */

const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);
const sqlite3 = require('sqlite3').verbose();

const CONFIG_FILE = path.join(__dirname, 'config.json');
const DB_FILE = path.join(__dirname, 'token-costs.db');
const SCHEMA_FILE = path.join(__dirname, 'db-schema.sql');
const OPENCLAW_BIN = '/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw';

// Load configuration
let config;
try {
    config = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
} catch (error) {
    console.error('❌ Failed to load config.json:', error.message);
    process.exit(1);
}

// Database setup
let db;

function initDatabase() {
    return new Promise((resolve, reject) => {
        db = new sqlite3.Database(DB_FILE, (err) => {
            if (err) return reject(err);
            
            // Load schema
            const schema = fs.readFileSync(SCHEMA_FILE, 'utf-8');
            db.exec(schema, (err) => {
                if (err) return reject(err);
                console.log('✅ Database initialized');
                resolve();
            });
        });
    });
}

function parseTokenString(tokenStr) {
    // Parse "31k/1000k (3%)" format
    const match = tokenStr.match(/(\d+(?:\.\d+)?)(k|m)?\/(\d+(?:\.\d+)?)(k|m)?\s*\((\d+)%\)/i);
    if (!match) return null;
    
    const used = parseFloat(match[1]) * (match[2]?.toLowerCase() === 'm' ? 1000 : 1);
    const total = parseFloat(match[3]) * (match[4]?.toLowerCase() === 'm' ? 1000 : 1);
    const percent = parseInt(match[5]);
    
    return {
        used: used * 1000, // Convert k to actual tokens
        total: total * 1000,
        percent
    };
}

function calculateCost(model, tokensInput, tokensOutput) {
    const pricing = config.pricing[model] || config.pricing['claude-sonnet-4-5']; // Default fallback
    
    const costInput = (tokensInput / pricing.per_tokens) * pricing.input;
    const costOutput = (tokensOutput / pricing.per_tokens) * pricing.output;
    
    return {
        costInput: parseFloat(costInput.toFixed(6)),
        costOutput: parseFloat(costOutput.toFixed(6)),
        costTotal: parseFloat((costInput + costOutput).toFixed(6))
    };
}

async function parseOpenClawStatus() {
    try {
        const { stdout } = await execPromise(`${OPENCLAW_BIN} status --sessions`);
        
        // Find Sessions table
        const sessionsMatch = stdout.match(/Sessions\n([\s\S]*?)(?=\n\n|$)/);
        if (!sessionsMatch) {
            console.error('❌ Could not find Sessions table in output');
            return [];
        }
        
        const sessionsText = sessionsMatch[1];
        const lines = sessionsText.split('\n');
        
        const sessions = [];
        
        for (const line of lines) {
            // Skip header and separator lines
            if (line.includes('───') || line.includes('Key') || line.includes('│ Key')) continue;
            
            // Match session line: │ session-key │ kind │ age │ model │ tokens │
            const match = line.match(/│\s*([^\s│]+(?:[^\│]*?))\s*│\s*([^\s│]+)\s*│\s*([^\│]+?)\s*│\s*([^\s│]+)\s*│\s*([^\│]+?)\s*│/);
            
            if (match) {
                const [, sessionKey, kind, age, model, tokens] = match;
                const tokenData = parseTokenString(tokens.trim());
                
                if (tokenData) {
                    // Estimate input/output split based on configured ratio
                    const inputRatio = config.collection.input_output_ratio;
                    const tokensInput = Math.round(tokenData.used * inputRatio);
                    const tokensOutput = tokenData.used - tokensInput;
                    
                    const costs = calculateCost(model.trim(), tokensInput, tokensOutput);
                    
                    sessions.push({
                        sessionKey: sessionKey.trim(),
                        kind: kind.trim(),
                        age: age.trim(),
                        model: model.trim(),
                        tokensUsed: tokenData.used,
                        tokensTotal: tokenData.total,
                        tokensInput,
                        tokensOutput,
                        ...costs
                    });
                }
            }
        }
        
        return sessions;
        
    } catch (error) {
        console.error('❌ Error parsing openclaw status:', error.message);
        return [];
    }
}

function storeSessions(sessions) {
    return new Promise((resolve, reject) => {
        const timestamp = Date.now();
        const stmt = db.prepare(`
            INSERT INTO token_usage 
            (timestamp, session_key, model, tokens_used, tokens_total, tokens_input, tokens_output, 
             cost_input, cost_output, cost_total, session_age)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `);
        
        let insertCount = 0;
        sessions.forEach(s => {
            stmt.run([
                timestamp,
                s.sessionKey,
                s.model,
                s.tokensUsed,
                s.tokensTotal,
                s.tokensInput,
                s.tokensOutput,
                s.costInput,
                s.costOutput,
                s.costTotal,
                s.age
            ], (err) => {
                if (err) console.error('Error inserting session:', err.message);
                else insertCount++;
            });
        });
        
        stmt.finalize((err) => {
            if (err) return reject(err);
            console.log(`✅ Stored ${insertCount} session records`);
            resolve();
        });
    });
}

async function checkBudgets() {
    return new Promise((resolve, reject) => {
        const now = new Date();
        const today = now.toISOString().split('T')[0];
        
        // Get spending for today, this week, this month
        const periods = {
            daily: `datetime('now', 'start of day')`,
            weekly: `datetime('now', '-7 days')`,
            monthly: `datetime('now', 'start of month')`
        };
        
        const alerts = [];
        
        Object.entries(periods).forEach(([period, dateFilter]) => {
            if (!config.budgets[period]?.enabled) return;
            
            db.get(`
                SELECT SUM(cost_total) as total_spent
                FROM token_usage
                WHERE created_at >= ${dateFilter}
            `, (err, row) => {
                if (err) {
                    console.error(`Error checking ${period} budget:`, err.message);
                    return;
                }
                
                const spent = row?.total_spent || 0;
                const limit = config.budgets[period].limit;
                const percentage = (spent / limit) * 100;
                
                console.log(`💰 ${period.toUpperCase()} Budget: $${spent.toFixed(2)} / $${limit.toFixed(2)} (${percentage.toFixed(1)}%)`);
                
                // Check thresholds
                config.budgets[period].alert_thresholds.forEach(threshold => {
                    if (percentage >= threshold * 100 && percentage < (threshold * 100 + 5)) {
                        alerts.push({
                            type: 'budget_warning',
                            severity: threshold >= 1.0 ? 'critical' : threshold >= 0.9 ? 'warning' : 'info',
                            message: `${period.toUpperCase()} budget ${threshold >= 1.0 ? 'EXCEEDED' : `at ${(threshold*100).toFixed(0)}%`}`,
                            details: JSON.stringify({
                                period,
                                spent,
                                limit,
                                percentage,
                                threshold
                            })
                        });
                    }
                });
            });
        });
        
        // Store alerts
        if (alerts.length > 0) {
            setTimeout(() => storeAlerts(alerts).then(resolve), 500);
        } else {
            resolve();
        }
    });
}

function storeAlerts(alerts) {
    return new Promise((resolve, reject) => {
        const stmt = db.prepare(`
            INSERT INTO alerts (timestamp, type, severity, message, details)
            VALUES (?, ?, ?, ?, ?)
        `);
        
        alerts.forEach(alert => {
            stmt.run([Date.now(), alert.type, alert.severity, alert.message, alert.details]);
        });
        
        stmt.finalize((err) => {
            if (err) return reject(err);
            console.log(`🚨 Created ${alerts.length} alert(s)`);
            resolve();
        });
    });
}

async function cleanup() {
    return new Promise((resolve) => {
        const cutoff = config.collection.retention_days;
        db.run(`
            DELETE FROM token_usage 
            WHERE created_at < datetime('now', '-${cutoff} days')
        `, function(err) {
            if (err) console.error('Error cleaning up old data:', err.message);
            else if (this.changes > 0) console.log(`🧹 Cleaned up ${this.changes} old records`);
            resolve();
        });
    });
}

async function main() {
    try {
        await initDatabase();
        
        console.log('📊 Collecting token usage data...');
        const sessions = await parseOpenClawStatus();
        
        if (sessions.length === 0) {
            console.log('⚠️  No sessions found');
            return;
        }
        
        console.log(`📋 Found ${sessions.length} active sessions`);
        
        // Calculate total cost for this collection
        const totalCost = sessions.reduce((sum, s) => sum + s.costTotal, 0);
        console.log(`💵 Current total cost: $${totalCost.toFixed(4)}`);
        
        await storeSessions(sessions);
        await checkBudgets();
        await cleanup();
        
        console.log('✅ Collection complete');
        
    } catch (error) {
        console.error('❌ Fatal error:', error.message);
        process.exit(1);
    } finally {
        if (db) {
            db.close((err) => {
                if (err) console.error('Error closing database:', err.message);
            });
        }
    }
}

// Run
main();
