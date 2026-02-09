const { spawn } = require('child_process');
const chalk = require('chalk');
const ora = require('ora');

async function destroyAgent(name, options) {
  const spinner = ora(`Destroying agent ${name}...`).start();

  try {
    const containerName = `openclaw-agent-${name}`;
    const volumeName = `openclaw-agent-${name}`;

    // Stop container if running
    spinner.text = 'Stopping container...';
    await stopContainer(containerName).catch(() => {});

    // Remove container
    spinner.text = 'Removing container...';
    const rmArgs = ['rm'];
    if (options.force) rmArgs.push('-f');
    rmArgs.push(containerName);
    
    await dockerCommand(rmArgs);

    // Remove volume if requested
    if (options.volumes) {
      spinner.text = 'Removing volumes...';
      await dockerCommand(['volume', 'rm', volumeName]).catch(() => {
        // Volume might not exist, ignore error
      });
    }

    spinner.succeed(chalk.green(`Agent ${name} destroyed successfully`));

  } catch (error) {
    spinner.fail(chalk.red('Failed to destroy agent'));
    console.error(chalk.red(error.message));
    process.exit(1);
  }
}

function stopContainer(containerName) {
  return dockerCommand(['stop', containerName]);
}

function dockerCommand(args) {
  return new Promise((resolve, reject) => {
    const proc = spawn('docker', args, {
      stdio: 'pipe'
    });

    let stderr = '';

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(stderr));
      }
    });
  });
}

module.exports = destroyAgent;
