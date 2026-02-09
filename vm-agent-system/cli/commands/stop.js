const { execSync } = require('child_process');
const chalk = require('chalk');
const ora = require('ora');

async function stopCommand(name, options) {
  const spinner = ora(`Stopping agent ${name}...`).start();

  try {
    execSync(`multipass stop ${name}`, { stdio: 'pipe' });
    spinner.succeed(chalk.green(`Agent ${name} stopped`));
  } catch (error) {
    spinner.fail(chalk.red('Failed to stop agent'));
    console.error(chalk.red('Error:'), error.message);
    process.exit(1);
  }
}

module.exports = stopCommand;
