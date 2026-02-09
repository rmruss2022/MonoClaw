const { spawn } = require('child_process');
const Table = require('cli-table3');
const chalk = require('chalk');

async function listAgents(options) {
  try {
    const containers = await getAgentContainers(options.all);

    if (containers.length === 0) {
      console.log(chalk.yellow('No agents found'));
      console.log('\nCreate one with:');
      console.log(`  ${chalk.cyan('docker-agent create <name> --profile <profile>')}`);
      return;
    }

    // Create table
    const table = new Table({
      head: ['Name', 'Status', 'Profile', 'CPU/Memory', 'Created', 'Container ID'],
      style: {
        head: ['cyan']
      }
    });

    containers.forEach(container => {
      const name = container.name.replace('openclaw-agent-', '');
      const status = container.state === 'running' 
        ? chalk.green('●  Running') 
        : chalk.gray('○  Stopped');
      
      table.push([
        name,
        status,
        container.profile || 'default',
        `${container.cpus || 'N/A'} / ${container.memory || 'N/A'}`,
        container.created,
        container.id.substring(0, 12)
      ]);
    });

    console.log(table.toString());
    console.log(`\nTotal agents: ${containers.length}`);

  } catch (error) {
    console.error(chalk.red('Error listing agents:', error.message));
    process.exit(1);
  }
}

function getAgentContainers(showAll = false) {
  return new Promise((resolve, reject) => {
    const args = [
      'ps',
      '--filter', 'name=openclaw-agent-',
      '--format', '{{.ID}}\t{{.Names}}\t{{.State}}\t{{.CreatedAt}}\t{{.Label "profile"}}\t{{.Label "cpus"}}\t{{.Label "memory"}}'
    ];

    if (showAll) {
      args.push('-a');
    }

    const proc = spawn('docker', args);

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code === 0) {
        const lines = stdout.trim().split('\n').filter(line => line);
        const containers = lines.map(line => {
          const [id, name, state, created, profile, cpus, memory] = line.split('\t');
          return {
            id,
            name,
            state,
            created,
            profile: profile || 'default',
            cpus: cpus || 'N/A',
            memory: memory || 'N/A'
          };
        });
        resolve(containers);
      } else {
        reject(new Error(`Docker command failed: ${stderr}`));
      }
    });
  });
}

module.exports = listAgents;
