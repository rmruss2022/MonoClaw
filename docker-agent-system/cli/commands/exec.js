const { spawn } = require('child_process');
const chalk = require('chalk');

async function execCommand(name, commandArray, options) {
  try {
    const containerName = `openclaw-agent-${name}`;
    const command = commandArray.join(' ');

    const args = ['exec'];
    
    if (options.interactive) args.push('-i');
    if (options.tty || process.stdin.isTTY) args.push('-t');
    
    args.push(containerName, 'sh', '-c', command);

    const proc = spawn('docker', args, {
      stdio: 'inherit'
    });

    proc.on('close', (code) => {
      process.exit(code);
    });

  } catch (error) {
    console.error(chalk.red('Error executing command:', error.message));
    process.exit(1);
  }
}

module.exports = execCommand;
