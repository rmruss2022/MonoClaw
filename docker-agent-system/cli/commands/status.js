const { spawn } = require('child_process');
const chalk = require('chalk');

async function getStatus(name) {
  try {
    const containerName = `openclaw-agent-${name}`;
    
    const inspect = await dockerInspect(containerName);
    
    if (!inspect) {
      console.error(chalk.red(`Agent ${name} not found`));
      process.exit(1);
    }

    const state = inspect.State;
    const config = inspect.Config;
    const hostConfig = inspect.HostConfig;

    console.log(chalk.bold(`\n📦 Agent: ${chalk.cyan(name)}\n`));

    // Status
    const status = state.Running ? chalk.green('Running') : chalk.red('Stopped');
    console.log(`${chalk.bold('Status:')} ${status}`);
    
    if (state.Running) {
      const uptime = getUptime(state.StartedAt);
      console.log(`${chalk.bold('Uptime:')} ${uptime}`);
    }

    // Profile
    const profile = config.Labels?.profile || 'default';
    console.log(`${chalk.bold('Profile:')} ${profile}`);

    // Container ID
    console.log(`${chalk.bold('Container:')} ${inspect.Id.substring(0, 12)}`);

    // Resources
    console.log(`\n${chalk.bold('Resources:')}`);
    console.log(`  CPU: ${hostConfig.NanoCpus / 1e9 || 'unlimited'} cores`);
    console.log(`  Memory: ${hostConfig.Memory ? `${hostConfig.Memory / 1024 / 1024 / 1024}G` : 'unlimited'}`);

    // Network
    console.log(`\n${chalk.bold('Network:')}`);
    const networks = Object.keys(inspect.NetworkSettings.Networks);
    networks.forEach(net => {
      const netInfo = inspect.NetworkSettings.Networks[net];
      console.log(`  ${net}: ${netInfo.IPAddress || 'N/A'}`);
    });

    // Volumes
    console.log(`\n${chalk.bold('Volumes:')}`);
    const mounts = inspect.Mounts || [];
    if (mounts.length > 0) {
      mounts.forEach(mount => {
        console.log(`  ${mount.Name || mount.Source} → ${mount.Destination}`);
      });
    } else {
      console.log(`  None`);
    }

    // Health
    if (state.Health) {
      console.log(`\n${chalk.bold('Health:')}`);
      const health = state.Health.Status === 'healthy' 
        ? chalk.green('Healthy') 
        : chalk.red(state.Health.Status);
      console.log(`  ${health}`);
    }

    console.log('');

  } catch (error) {
    console.error(chalk.red('Error getting status:', error.message));
    process.exit(1);
  }
}

function dockerInspect(containerName) {
  return new Promise((resolve, reject) => {
    const proc = spawn('docker', ['inspect', containerName]);

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
        try {
          const data = JSON.parse(stdout);
          resolve(data[0]);
        } catch (e) {
          reject(new Error('Failed to parse Docker inspect output'));
        }
      } else {
        resolve(null);
      }
    });
  });
}

function getUptime(startedAt) {
  const start = new Date(startedAt);
  const now = new Date();
  const diff = now - start;

  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

module.exports = getStatus;
