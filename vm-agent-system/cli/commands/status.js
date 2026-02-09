const http = require('http');
const chalk = require('chalk');

async function statusCommand(name, options) {
  async function showStatus() {
    try {
      const data = await httpGet(`http://localhost:9091/agents/${name}/status`);
      const agent = data.agent;

      console.clear();
      console.log(chalk.bold.cyan(`\n╔═══ Agent Status: ${name} ═══╗\n`));
      
      const statusColor = agent.status === 'online' ? chalk.green : chalk.red;
      console.log(`  Status:      ${statusColor(agent.status)}`);
      console.log(`  Type:        ${agent.metadata.type || 'generic'}`);
      console.log(`  IP:          ${agent.metadata.vmIp || 'N/A'}`);
      console.log(`  Registered:  ${new Date(agent.registeredAt).toLocaleString()}`);
      
      if (agent.lastSeen) {
        console.log(`  Last Seen:   ${new Date(agent.lastSeen).toLocaleString()}`);
      }

      console.log(chalk.bold('\n  Resources:'));
      console.log(`  CPU:         ${agent.metadata.cpu || 'N/A'} cores (${agent.health.cpu || 'N/A'}% used)`);
      console.log(`  Memory:      ${agent.metadata.memory || 'N/A'} (${agent.health.memory ? agent.health.memory.usagePercent.toFixed(1) + '%' : 'N/A'} used)`);
      console.log(`  Disk:        ${agent.metadata.disk || 'N/A'} (${agent.health.disk ? agent.health.disk.usagePercent.toFixed(1) + '%' : 'N/A'} used)`);

      console.log(chalk.bold('\n  Statistics:'));
      console.log(`  Tasks Received:   ${agent.stats.tasksReceived}`);
      console.log(`  Tasks Completed:  ${agent.stats.tasksCompleted}`);
      console.log(`  Tasks Failed:     ${agent.stats.tasksFailed}`);
      console.log(`  Messages Sent:    ${agent.stats.messagesSent}`);
      console.log(`  Messages Received: ${agent.stats.messagesReceived}`);

      if (agent.currentTasks.length > 0) {
        console.log(chalk.bold('\n  Active Tasks:'));
        agent.currentTasks.forEach((task, i) => {
          console.log(`  ${i + 1}. ${task.type} (started ${new Date(task.startedAt).toLocaleString()})`);
        });
      } else {
        console.log(chalk.bold('\n  Active Tasks:'), chalk.gray('none'));
      }

      if (agent.metadata.capabilities) {
        console.log(chalk.bold('\n  Capabilities:'), agent.metadata.capabilities);
      }

      console.log(chalk.bold.cyan(`\n╚${'═'.repeat(name.length + 20)}╝\n`));

      if (options.watch) {
        console.log(chalk.gray('Refreshing in 5 seconds... (Ctrl+C to exit)'));
      }

    } catch (error) {
      if (error.message.includes('404')) {
        console.error(chalk.red(`Agent ${name} not found`));
      } else {
        console.error(chalk.red('Error:'), error.message);
      }
      
      if (!options.watch) {
        process.exit(1);
      }
    }
  }

  await showStatus();

  if (options.watch) {
    setInterval(showStatus, 5000);
  }
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

module.exports = statusCommand;
