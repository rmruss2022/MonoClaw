const http = require('http');
const chalk = require('chalk');
const ora = require('ora');

async function taskCommand(name, taskJson, options) {
  let task;
  
  try {
    task = JSON.parse(taskJson);
  } catch (error) {
    console.error(chalk.red('Invalid JSON:'), error.message);
    process.exit(1);
  }

  const spinner = ora('Sending task to agent...').start();

  try {
    const result = await httpPost(`http://localhost:9091/agents/${name}/task`, task);
    spinner.succeed(chalk.green(`Task sent: ${result.taskId}`));
    
    if (options.wait) {
      spinner.start('Waiting for task completion...');
      
      // Poll for completion (simplified - real implementation would use WebSocket)
      const timeout = parseInt(options.timeout);
      const startTime = Date.now();
      
      while (Date.now() - startTime < timeout) {
        await sleep(2000);
        
        const status = await httpGet(`http://localhost:9091/agents/${name}/status`);
        const activeTask = status.agent.currentTasks.find(t => t.id === result.taskId);
        
        if (!activeTask) {
          spinner.succeed(chalk.green('Task completed'));
          break;
        }
      }
    }

  } catch (error) {
    spinner.fail(chalk.red('Failed to send task'));
    console.error(chalk.red('Error:'), error.message);
    process.exit(1);
  }
}

function httpPost(url, data) {
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

function httpGet(url) {
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

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

module.exports = taskCommand;
