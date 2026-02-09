const { execSync } = require('child_process');
const chalk = require('chalk');
const ora = require('ora');

async function startCommand(name, options) {
  const spinner = ora(`Starting agent ${name}...`).start();

  try {
    execSync(`multipass start ${name}`, { stdio: 'pipe' });
    spinner.succeed(chalk.green(`Agent ${name} started`));
    
    // Wait a moment for the service to start
    spinner.text = 'Waiting for agent service...';
    await sleep(5000);
    
    spinner.succeed(chalk.green('Agent is ready'));
    
  } catch (error) {
    spinner.fail(chalk.red('Failed to start agent'));
    console.error(chalk.red('Error:'), error.message);
    process.exit(1);
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

module.exports = startCommand;
