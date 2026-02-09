const { spawn } = require('child_process');
const chalk = require('chalk');

async function openShell(name, options) {
  try {
    const containerName = `openclaw-agent-${name}`;
    const shell = options.shell || '/bin/bash';

    console.log(chalk.gray(`Opening shell in ${name}... (exit with Ctrl+D or 'exit')\n`));

    const proc = spawn('docker', ['exec', '-it', containerName, shell], {
      stdio: 'inherit'
    });

    proc.on('close', (code) => {
      process.exit(code);
    });

  } catch (error) {
    console.error(chalk.red('Error opening shell:', error.message));
    process.exit(1);
  }
}

module.exports = openShell;
