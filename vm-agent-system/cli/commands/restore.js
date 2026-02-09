const { execSync } = require('child_process');
const chalk = require('chalk');
const ora = require('ora');

async function restoreCommand(name, snapshotName, options) {
  const spinner = ora(`Restoring from snapshot: ${snapshotName}`).start();

  try {
    execSync(`multipass restore ${name} --snapshot ${snapshotName}`, { stdio: 'pipe' });
    spinner.succeed(chalk.green(`Agent restored from snapshot: ${snapshotName}`));
    
    // Restart the agent service
    spinner.text = 'Restarting agent service...';
    execSync(`multipass exec ${name} -- sudo systemctl restart vm-agent`, { stdio: 'pipe' });
    spinner.succeed(chalk.green('Agent service restarted'));
    
  } catch (error) {
    spinner.fail(chalk.red('Failed to restore snapshot'));
    console.error(chalk.red('Error:'), error.message);
    process.exit(1);
  }
}

module.exports = restoreCommand;
