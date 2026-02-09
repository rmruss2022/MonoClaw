const { spawn } = require('child_process');
const chalk = require('chalk');
const ora = require('ora');

async function stopAgent(name, options) {
  const spinner = ora(`Stopping agent ${name}...`).start();

  try {
    const containerName = `openclaw-agent-${name}`;
    
    const args = ['stop'];
    if (options.time) args.push('-t', options.time);
    args.push(containerName);

    await dockerCommand(args);

    spinner.succeed(chalk.green(`Agent ${name} stopped successfully`));

  } catch (error) {
    spinner.fail(chalk.red('Failed to stop agent'));
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

module.exports = stopAgent;
