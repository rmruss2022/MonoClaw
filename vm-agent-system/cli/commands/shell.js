const { spawn } = require('child_process');
const chalk = require('chalk');

async function shellCommand(name, options) {
  console.log(chalk.gray(`Opening shell to ${name}...`));
  console.log(chalk.gray('Type "exit" to close the shell'));
  console.log('');

  const proc = spawn('multipass', ['shell', name], {
    stdio: 'inherit'
  });

  proc.on('error', (error) => {
    console.error(chalk.red('Failed to open shell:'), error.message);
    process.exit(1);
  });
}

module.exports = shellCommand;
