const { spawn } = require('child_process');
const chalk = require('chalk');
const ora = require('ora');

async function startAgent(name) {
  const spinner = ora(`Starting agent ${name}...`).start();

  try {
    const containerName = `openclaw-agent-${name}`;

    await dockerCommand(['start', containerName]);

    spinner.succeed(chalk.green(`Agent ${name} started successfully`));

  } catch (error) {
    spinner.fail(chalk.red('Failed to start agent'));
    console.error(chalk.red(error.message));
    process.exit(1);
  }
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

module.exports = startAgent;
