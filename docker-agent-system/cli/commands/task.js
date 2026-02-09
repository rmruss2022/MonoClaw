const { spawn } = require('child_process');
const chalk = require('chalk');
const ora = require('ora');

async function sendTask(name, taskJson) {
  const spinner = ora('Sending task...').start();

  try {
    const containerName = `openclaw-agent-${name}`;
    
    // Parse task JSON
    let task;
    try {
      task = JSON.parse(taskJson);
    } catch (e) {
      throw new Error('Invalid JSON: ' + e.message);
    }

    // Validate task
    if (!task.type) {
      throw new Error('Task must have a "type" field');
    }

    // For exec tasks, we can run them directly in the container
    if (task.type === 'exec') {
      spinner.text = 'Executing command...';
      const result = await execInContainer(containerName, task.command, task.cwd);
      spinner.succeed(chalk.green('Task completed'));
      
      console.log('\nOutput:');
      console.log(result);
      return;
    }

    // For other tasks, we'd need to send via hub WebSocket
    // For now, show a message
    spinner.warn(chalk.yellow('Complex task types require hub integration'));
    console.log('\nTask to send:', JSON.stringify(task, null, 2));
    console.log('\nTo send complex tasks, use the hub API or WebSocket directly');

  } catch (error) {
    spinner.fail(chalk.red('Failed to send task'));
    console.error(chalk.red(error.message));
    process.exit(1);
  }
}

function execInContainer(containerName, command, cwd) {
  return new Promise((resolve, reject) => {
    const shellCmd = cwd ? `cd ${cwd} && ${command}` : command;
    
    const proc = spawn('docker', ['exec', containerName, 'sh', '-c', shellCmd], {
      stdio: 'pipe'
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code === 0) {
        resolve(stdout);
      } else {
        reject(new Error(stderr || `Command exited with code ${code}`));
      }
    });
  });
}

module.exports = sendTask;
