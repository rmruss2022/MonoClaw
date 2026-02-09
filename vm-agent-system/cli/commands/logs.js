const { spawn } = require('child_process');
const chalk = require('chalk');

async function logsCommand(name, options) {
  const args = ['exec', name, '--', 'sudo', 'journalctl', '-u', 'vm-agent'];

  if (options.follow) {
    args.push('-f');
  }

  if (options.lines) {
    args.push('-n', options.lines);
  }

  console.log(chalk.gray(`Showing logs for ${name}...`));
  console.log(chalk.gray('Press Ctrl+C to exit'));
  console.log('');

  const proc = spawn('multipass', args, {
    stdio: 'inherit'
  });

  proc.on('error', (error) => {
    console.error(chalk.red('Failed to get logs:'), error.message);
    process.exit(1);
  });
}

module.exports = logsCommand;
