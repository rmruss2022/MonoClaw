#!/usr/bin/env node

/**
 * Interviewer Research Automation
 * 
 * Scans calendar interviews, finds interviewers on LinkedIn,
 * and adds their background to the job tracker.
 */

const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

const DATA_PATH = path.join(__dirname, 'data.json');
const PROCESSED_PATH = path.join(__dirname, 'processed-interviewers.json');

// Track which interviewers we've already researched
function loadProcessed() {
    try {
        return JSON.parse(fs.readFileSync(PROCESSED_PATH, 'utf-8'));
    } catch {
        return { interviewers: {} };
    }
}

function saveProcessed(data) {
    fs.writeFileSync(PROCESSED_PATH, JSON.stringify(data, null, 2));
}

// Extract interviewer name from interview type
function extractInterviewerName(interviewType) {
    // Patterns:
    // "Call with Meg Marks" -> "Meg Marks"
    // "Interview with Sean (Principal Eng)" -> "Sean"
    // "Intro call with Tyler Ichikawa" -> "Tyler Ichikawa"
    
    const patterns = [
        /(?:Call|Interview|Intro call|Meeting|Chat)\s+with\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)/i,
        /([A-Z][a-z]+\s+[A-Z][a-z]+)/  // Fallback: any capitalized name
    ];
    
    for (const pattern of patterns) {
        const match = interviewType.match(pattern);
        if (match) {
            return match[1].trim();
        }
    }
    
    return null;
}

// Search for interviewer on LinkedIn using web_search
async function searchLinkedIn(name, company) {
    const query = `${name} ${company} site:linkedin.com/in`;
    console.log(`Searching LinkedIn: ${query}`);
    
    // Use OpenClaw's web_search via the API
    try {
        const response = await fetch('http://127.0.0.1:18789/api/tools/web_search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer dab4590ec82b21404c36ca9b6ce82438246a56c480972d24'
            },
            body: JSON.stringify({
                query,
                count: 3
            })
        });
        
        const data = await response.json();
        
        // Find the best LinkedIn profile match
        if (data.results && data.results.length > 0) {
            for (const result of data.results) {
                if (result.url && result.url.includes('linkedin.com/in/')) {
                    return {
                        url: result.url,
                        title: result.title,
                        description: result.description
                    };
                }
            }
        }
        
        return null;
    } catch (error) {
        console.error('LinkedIn search failed:', error);
        return null;
    }
}

// Create a summary from LinkedIn profile info
function createSummary(linkedInData, name) {
    if (!linkedInData) {
        return `${name} - LinkedIn profile not found`;
    }
    
    // Extract key info from title/description
    const title = linkedInData.title || '';
    const description = linkedInData.description || '';
    
    // Title usually contains: Name - Current Role at Company
    const roleMatch = title.match(/[-–]\s*(.+?)\s*(?:at|@)\s*(.+?)(?:\s*[-–|]|$)/);
    
    let summary = `**${name}**\n`;
    
    if (roleMatch) {
        summary += `Current: ${roleMatch[1].trim()} at ${roleMatch[2].trim()}\n`;
    }
    
    if (description) {
        // Clean up description (often has ... at end)
        const cleanDesc = description.replace(/\s*\.\.\.$/, '').trim();
        summary += `\nBackground: ${cleanDesc}`;
    }
    
    summary += `\n\n🔗 ${linkedInData.url}`;
    
    return summary;
}

async function processInterviews() {
    console.log('Starting interviewer research...');
    
    // Load data
    const data = JSON.parse(fs.readFileSync(DATA_PATH, 'utf-8'));
    const processed = loadProcessed();
    let updated = false;
    
    for (const company of data.companies) {
        if (!company.interviews || company.interviews.length === 0) continue;
        
        for (const interview of company.interviews) {
            // Extract interviewer name
            const interviewerName = extractInterviewerName(interview.type);
            
            if (!interviewerName) {
                console.log(`No interviewer found in: ${interview.type}`);
                continue;
            }
            
            // Check if already processed
            const key = `${company.name}:${interviewerName}`;
            if (processed.interviewers[key]) {
                console.log(`Already processed: ${interviewerName} at ${company.name}`);
                continue;
            }
            
            // Check if interview already has interviewer data
            if (interview.interviewer) {
                console.log(`Interviewer data already exists: ${interviewerName}`);
                processed.interviewers[key] = true;
                continue;
            }
            
            console.log(`\nResearching: ${interviewerName} at ${company.name}`);
            
            // Search LinkedIn
            const linkedInData = await searchLinkedIn(interviewerName, company.name);
            
            // Create summary
            const summary = createSummary(linkedInData, interviewerName);
            
            // Add to interview record
            interview.interviewer = {
                name: interviewerName,
                linkedin: linkedInData?.url || null,
                summary: summary,
                researchedAt: new Date().toISOString()
            };
            
            // Mark as processed
            processed.interviewers[key] = true;
            updated = true;
            
            console.log(`✓ Added interviewer data for ${interviewerName}`);
            
            // Rate limit - wait between searches
            await new Promise(resolve => setTimeout(resolve, 2000));
        }
    }
    
    if (updated) {
        // Save updated data
        fs.writeFileSync(DATA_PATH, JSON.stringify(data, null, 2));
        saveProcessed(processed);
        console.log('\n✓ Job tracker updated with interviewer research');
    } else {
        console.log('\nNo new interviewers to research');
    }
}

// Run
processInterviews().catch(console.error);
