const { execSync } = require('child_process');
const chalk = require('chalk');
const ora = require('ora');

async function snapshotCommand(name, snapshotName, options) {
  const finalName = snapshotName || `snapshot-${Date.now()}`;
  const spinner = ora(`Creating snapshot: ${finalName}`).start();

  try {
    execSync(`multipass snapshot ${name} --name ${finalName}`, { stdio: 'pipe' });
    spinner.succeed(chalk.green(`Snapshot created: ${finalName}`));
  } catch (error) {
    spinner.fail(chalk.red('Failed to create snapshot'));
    console.error(chalk.red('Error:'), error.message);
    process.exit(1);
  }
}

module.exports = snapshotCommand;
