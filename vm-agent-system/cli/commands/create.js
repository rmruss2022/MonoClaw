const { spawn } = require('child_process');
const path = require('path');
const chalk = require('chalk');
const ora = require('ora');
const { loadProfile } = require('./profiles');

async function createCommand(name, options) {
  const spinner = ora('Creating VM agent...').start();

  // Load profile if specified
  let profile = null;
  if (options.profile) {
    try {
      profile = loadProfile(options.profile);
      spinner.info(`Using profile: ${profile.name}`);
      
      // Merge profile settings with command options (options override profile)
      options.cpu = options.cpu || profile.resources.cpu;
      options.memory = options.memory || profile.resources.memory;
      options.disk = options.disk || profile.resources.disk;
      options.type = options.type || profile.name;
    } catch (error) {
      spinner.fail(chalk.red(error.message));
      process.exit(1);
    }
  }

  const scriptPath = path.join(__dirname, '../../provisioning/create-agent.sh');
  
  const args = [
    '--name', name,
    '--type', options.type,
    '--cpu', options.cpu,
    '--memory', options.memory,
    '--disk', options.disk
  ];

  if (options.capabilities) {
    args.push('--capabilities', options.capabilities);
  }

  if (options.hubUrl) {
    args.push('--hub-url', options.hubUrl);
  }

  // Pass profile path if using one
  if (profile) {
    const profilePath = path.join(__dirname, '../../profiles', `${options.profile}.json`);
    args.push('--profile', profilePath);
  }

  const proc = spawn(scriptPath, args, {
    stdio: 'inherit'
  });

  return new Promise((resolve, reject) => {
    proc.on('close', (code) => {
      if (code === 0) {
        spinner.succeed(chalk.green(`Agent ${name} created successfully`));
        if (profile) {
          console.log(chalk.cyan(`\n📦 Profile '${profile.name}' applied:`));
          console.log(chalk.gray(`  - ${profile.description}`));
          if (profile.packages) {
            console.log(chalk.gray(`  - Installed: ${profile.packages.join(', ')}`));
          }
        }
        resolve();
      } else {
        spinner.fail(chalk.red(`Failed to create agent (exit code ${code})`));
        reject(new Error(`Process exited with code ${code}`));
      }
    });

    proc.on('error', (error) => {
      spinner.fail(chalk.red('Failed to create agent'));
      reject(error);
    });
  });
}

module.exports = createCommand;
