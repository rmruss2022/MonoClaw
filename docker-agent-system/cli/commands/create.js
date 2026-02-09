const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs').promises;
const chalk = require('chalk');
const ora = require('ora');

const SYSTEM_ROOT = path.join(process.env.HOME, '.openclaw/workspace/docker-agent-system');
const PROVISIONING_DIR = path.join(SYSTEM_ROOT, 'provisioning');

async function createAgent(name, options) {
  const spinner = ora('Creating Docker agent...').start();

  try {
    // Validate name
    if (!/^[a-z0-9-]+$/.test(name)) {
      throw new Error('Agent name must contain only lowercase letters, numbers, and hyphens');
    }

    const containerName = `openclaw-agent-${name}`;
    
    // Check if agent already exists
    const exists = await checkAgentExists(containerName);
    if (exists) {
      throw new Error(`Agent ${name} already exists`);
    }

    spinner.text = 'Building base image...';
    await buildBaseImage();

    spinner.text = 'Creating agent container...';
    
    // Prepare profile path if specified
    const profilePath = options.profile 
      ? path.join(SYSTEM_ROOT, 'profiles', `${options.profile}.json`)
      : null;

    if (profilePath) {
      const profileExists = await fs.access(profilePath).then(() => true).catch(() => false);
      if (!profileExists) {
        throw new Error(`Profile not found: ${options.profile}`);
      }
    }

    // Call provisioning script
    await runProvisioningScript(name, {
      profile: options.profile,
      cpus: options.cpus,
      memory: options.memory,
      disk: options.disk
    });

    spinner.succeed(chalk.green(`Agent ${name} created successfully!`));
    
    console.log('\nNext steps:');
    console.log(`  ${chalk.cyan('docker-agent status ' + name)}    - Check agent status`);
    console.log(`  ${chalk.cyan('docker-agent exec ' + name + ' <cmd>')} - Run a command`);
    console.log(`  ${chalk.cyan('docker-agent shell ' + name)}   - Open interactive shell`);

  } catch (error) {
    spinner.fail(chalk.red('Failed to create agent'));
    console.error(chalk.red(error.message));
    process.exit(1);
  }
}

async function checkAgentExists(containerName) {
  return new Promise((resolve) => {
    const proc = spawn('docker', ['inspect', containerName]);
    proc.on('close', (code) => {
      resolve(code === 0);
    });
  });
}

async function buildBaseImage() {
  return new Promise((resolve, reject) => {
    const runtimeDir = path.join(SYSTEM_ROOT, 'agent-runtime');
    const proc = spawn('docker', ['build', '-t', 'openclaw-agent-base', '.'], {
      cwd: runtimeDir,
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
        reject(new Error(`Failed to build base image: ${stderr}`));
      }
    });
  });
}

async function runProvisioningScript(name, options) {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(PROVISIONING_DIR, 'create-agent.sh');
    
    const args = [name];
    if (options.profile) args.push('--profile', options.profile);
    if (options.cpus) args.push('--cpus', options.cpus);
    if (options.memory) args.push('--memory', options.memory);

    const proc = spawn(scriptPath, args, {
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
        reject(new Error(`Provisioning failed: ${stderr}`));
      }
    });
  });
}

module.exports = createAgent;
