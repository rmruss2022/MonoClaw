const http = require('http');
const chalk = require('chalk');
const Table = require('cli-table3');

async function listCommand(options) {
  try {
    const response = await fetch('http://localhost:9091/agents');
    const data = await response.json();

    if (!data.agents || data.agents.length === 0) {
      console.log(chalk.yellow('No agents registered'));
      return;
    }

    let agents = data.agents;

    // Apply filters
    if (options.status) {
      agents = agents.filter(a => a.status === options.status);
    }

    if (options.type) {
      agents = agents.filter(a => a.metadata.type === options.type);
    }

    // Create table
    const table = new Table({
      head: [
        chalk.cyan('Name'),
        chalk.cyan('Status'),
        chalk.cyan('Type'),
        chalk.cyan('CPU'),
        chalk.cyan('Memory'),
        chalk.cyan('Tasks'),
        chalk.cyan('Uptime')
      ],
      style: {
        head: [],
        border: []
      }
    });

    agents.forEach(agent => {
      const statusColor = agent.status === 'online' ? chalk.green : chalk.gray;
      const uptime = agent.health.uptime 
        ? formatUptime(agent.health.uptime)
        : 'N/A';

      table.push([
        agent.id,
        statusColor(agent.status),
        agent.metadata.type || 'generic',
        `${agent.health.cpu || 'N/A'}%`,
        agent.health.memory 
          ? `${agent.health.memory.usagePercent.toFixed(1)}%`
          : 'N/A',
        `${agent.currentTasks.length}`,
        uptime
      ]);
    });

    console.log(table.toString());
    console.log(`\nTotal: ${agents.length} agents`);

  } catch (error) {
    console.error(chalk.red('Error fetching agents:'), error.message);
    console.error(chalk.yellow('Is the hub server running? Start it with: npm run hub'));
    process.exit(1);
  }
}

function formatUptime(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  } else {
    return `${minutes}m`;
  }
}

// Polyfill for fetch in older Node versions
if (typeof fetch === 'undefined') {
  global.fetch = function(url) {
    return new Promise((resolve, reject) => {
      http.get(url, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          resolve({
            json: () => Promise.resolve(JSON.parse(data))
          });
        });
      }).on('error', reject);
    });
  };
}

module.exports = listCommand;
