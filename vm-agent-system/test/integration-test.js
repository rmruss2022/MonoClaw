#!/usr/bin/env node

/**
 * Integration test for VM Agent System
 * 
 * Tests hub server, agent connection, and task execution
 */

const http = require('http');
const { spawn } = require('child_process');
const path = require('path');

const HUB_URL = 'http://localhost:9091';
const TEST_AGENT_ID = 'test-agent-' + Date.now();

console.log('='.repeat(60));
console.log('VM Agent System Integration Test');
console.log('='.repeat(60));

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function httpGet(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(JSON.parse(data));
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${data}`));
        }
      });
    }).on('error', reject);
  });
}

async function httpPost(url, data) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const postData = JSON.stringify(data);

    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port,
      path: urlObj.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      }
    };

    const req = http.request(options, (res) => {
      let responseData = '';
      res.on('data', chunk => responseData += chunk);
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(JSON.parse(responseData));
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${responseData}`));
        }
      });
    });

    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

async function test(name, fn) {
  try {
    process.stdout.write(`\n[TEST] ${name} ... `);
    await fn();
    console.log('✓ PASS');
    return true;
  } catch (error) {
    console.log('✗ FAIL');
    console.error('  Error:', error.message);
    return false;
  }
}

async function main() {
  let passed = 0;
  let failed = 0;

  // Test 1: Hub health check
  if (await test('Hub server health check', async () => {
    const health = await httpGet(`${HUB_URL}/health`);
    if (!health.status || health.status !== 'healthy') {
      throw new Error('Hub not healthy');
    }
  })) passed++; else failed++;

  // Test 2: Register agent
  let token;
  if (await test('Register test agent', async () => {
    const result = await httpPost(`${HUB_URL}/agents/register`, {
      agentId: TEST_AGENT_ID,
      metadata: {
        type: 'test',
        capabilities: ['test'],
        cpu: 1,
        memory: '1G'
      }
    });
    
    if (!result.token) {
      throw new Error('No token received');
    }
    
    token = result.token;
  })) passed++; else failed++;

  // Test 3: List agents
  if (await test('List agents', async () => {
    const result = await httpGet(`${HUB_URL}/agents`);
    
    if (!result.agents || !Array.isArray(result.agents)) {
      throw new Error('Invalid agents list');
    }
    
    const found = result.agents.find(a => a.id === TEST_AGENT_ID);
    if (!found) {
      throw new Error('Test agent not found in list');
    }
  })) passed++; else failed++;

  // Test 4: Get agent status
  if (await test('Get agent status', async () => {
    const result = await httpGet(`${HUB_URL}/agents/${TEST_AGENT_ID}/status`);
    
    if (!result.agent || result.agent.id !== TEST_AGENT_ID) {
      throw new Error('Invalid agent status');
    }
  })) passed++; else failed++;

  // Test 5: Send task to offline agent (should queue)
  let taskId;
  if (await test('Send task to offline agent', async () => {
    const result = await httpPost(`${HUB_URL}/agents/${TEST_AGENT_ID}/task`, {
      type: 'exec',
      command: 'echo test'
    });
    
    if (!result.taskId) {
      throw new Error('No task ID received');
    }
    
    taskId = result.taskId;
  })) passed++; else failed++;

  // Test 6: Get stats
  if (await test('Get routing statistics', async () => {
    const result = await httpGet(`${HUB_URL}/admin/stats`);
    
    if (!result.router || !result.agents) {
      throw new Error('Invalid stats format');
    }
  })) passed++; else failed++;

  // Test 7: Get metrics
  if (await test('Prometheus metrics endpoint', async () => {
    const metrics = await new Promise((resolve, reject) => {
      http.get(`${HUB_URL}/metrics`, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          if (res.statusCode === 200) {
            resolve(data);
          } else {
            reject(new Error(`HTTP ${res.statusCode}`));
          }
        });
      }).on('error', reject);
    });
    
    if (!metrics.includes('vm_hub_')) {
      throw new Error('Invalid metrics format');
    }
  })) passed++; else failed++;

  // Test 8: Deregister agent
  if (await test('Deregister agent', async () => {
    await new Promise((resolve, reject) => {
      const urlObj = new URL(`${HUB_URL}/agents/${TEST_AGENT_ID}`);
      const options = {
        hostname: urlObj.hostname,
        port: urlObj.port,
        path: urlObj.pathname,
        method: 'DELETE'
      };

      const req = http.request(options, (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve();
        } else {
          reject(new Error(`HTTP ${res.statusCode}`));
        }
      });

      req.on('error', reject);
      req.end();
    });
  })) passed++; else failed++;

  // Summary
  console.log('\n' + '='.repeat(60));
  console.log('Test Summary');
  console.log('='.repeat(60));
  console.log(`Passed: ${passed}`);
  console.log(`Failed: ${failed}`);
  console.log(`Total:  ${passed + failed}`);
  console.log('='.repeat(60));

  if (failed > 0) {
    console.log('\n❌ Some tests failed');
    process.exit(1);
  } else {
    console.log('\n✅ All tests passed!');
    process.exit(0);
  }
}

// Check if hub is running
httpGet(`${HUB_URL}/health`)
  .then(() => {
    console.log('✓ Hub server is running\n');
    return main();
  })
  .catch(error => {
    console.error('\n❌ Hub server is not running');
    console.error('Start it with: cd hub && npm start');
    console.error('\nError:', error.message);
    process.exit(1);
  });
