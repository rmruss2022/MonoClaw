const { spawn } = require('child_process');
const chalk = require('chalk');

async function viewLogs(name, options) {
  try {
    const containerName = `openclaw-agent-${name}`;

    const args = ['logs'];
    
    if (options.follow) args.push('-f');
    if (options.tail) args.push('--tail', options.tail);
    
    args.push(containerName);

    const proc = spawn('docker', args, {
      stdio: 'inherit'
    });

    proc.on('close', (code) => {
      process.exit(code);
    });

  } catch (error) {
    console.error(chalk.red('Error viewing logs:', error.message));
    process.exit(1);
  }
}

module.exports = viewLogs;
