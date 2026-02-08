#!/usr/bin/env node

/**
 * Migrate Historical Token Data
 * Import usage-history.json into the new SQLite database
 */

const fs = require('fs');
const path = require('path');
const sqlite3 = require('sqlite3').verbose();

const HISTORY_FILE = path.join(__dirname, 'usage-history.json');
const DB_FILE = path.join(__dirname, 'token-costs.db');
const CONFIG_FILE = path.join(__dirname, 'config.json');

// Load config for pricing
const config = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));

// Load historical data
const history = JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf-8'));

console.log(`📦 Migrating ${history.length} historical data points...`);
console.log(`From: ${new Date(history[0].timestamp).toISOString()}`);
console.log(`To:   ${new Date(history[history.length - 1].timestamp).toISOString()}`);
console.log('');

const db = new sqlite3.Database(DB_FILE);

let imported = 0;
let skipped = 0;
let errors = 0;

// Helper to parse token strings
function parseTokens(tokenStr) {
    const num = parseInt(tokenStr.replace('k', '').replace('m', ''));
    if (tokenStr.includes('m')) return num * 1000;
    return num;
}

// Helper to calculate cost
function calculateCost(tokensK, model) {
    const pricing = config.pricing[model] || config.pricing['claude-sonnet-4-5'];
    const inputRatio = config.collection.input_output_ratio || 0.6;
    const outputRatio = 1 - inputRatio;
    
    const tokens = tokensK * 1000; // Convert k to actual count
    const inputTokens = tokens * inputRatio;
    const outputTokens = tokens * outputRatio;
    
    const inputCost = (inputTokens / pricing.per_tokens) * pricing.input;
    const outputCost = (outputTokens / pricing.per_tokens) * pricing.output;
    
    return inputCost + outputCost;
}

db.serialize(() => {
    // Prepare insert statement
    const stmt = db.prepare(`
        INSERT OR IGNORE INTO token_usage 
        (timestamp, session_key, model, tokens_input, tokens_output, tokens_used, tokens_total, cost_input, cost_output, cost_total, session_age)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    
    history.forEach((entry, idx) => {
        try {
            const tokensK = parseTokens(entry.tokensUsed);
            const totalK = parseTokens(entry.tokensTotal);
            const model = entry.model || 'claude-sonnet-4-5';
            
            // Estimate input/output split
            const inputRatio = config.collection.input_output_ratio || 0.6;
            const inputTokens = Math.floor(tokensK * 1000 * inputRatio);
            const outputTokens = Math.floor(tokensK * 1000 * (1 - inputRatio));
            
            const pricing = config.pricing[model] || config.pricing['claude-sonnet-4-5'];
            const costInput = (inputTokens / pricing.per_tokens) * pricing.input;
            const costOutput = (outputTokens / pricing.per_tokens) * pricing.output;
            const costTotal = costInput + costOutput;
            
            const sessionAge = `${entry.activeSessions} sessions`;
            
            stmt.run(
                entry.timestamp,
                'agent:main:main', // All historical data is from main session
                model,
                inputTokens,
                outputTokens,
                tokensK * 1000,
                totalK * 1000,
                costInput,
                costOutput,
                costTotal,
                sessionAge,
                (err) => {
                    if (err) {
                        if (err.message.includes('UNIQUE constraint')) {
                            skipped++;
                        } else {
                            console.error(`❌ Error on entry ${idx}:`, err.message);
                            errors++;
                        }
                    } else {
                        imported++;
                    }
                }
            );
            
        } catch (error) {
            console.error(`❌ Failed to process entry ${idx}:`, error.message);
            errors++;
        }
    });
    
    stmt.finalize(() => {
        console.log('');
        console.log('✅ Migration complete!');
        console.log(`   Imported: ${imported}`);
        console.log(`   Skipped:  ${skipped} (already exist)`);
        console.log(`   Errors:   ${errors}`);
        console.log('');
        
        // Calculate total historical cost
        db.get(
            'SELECT SUM(cost_total) as total_cost, COUNT(*) as count FROM token_usage WHERE session_key = ?',
            ['agent:main:main'],
            (err, row) => {
                if (!err && row) {
                    console.log(`💰 Historical data total cost: $${row.total_cost.toFixed(2)}`);
                    console.log(`📊 Data points in database: ${row.count}`);
                }
                db.close();
            }
        );
    });
});
