const { execSync } = require('child_process');
const chalk = require('chalk');

async function execCommand(name, commandParts, options) {
  const command = commandParts.join(' ');
  
  console.log(chalk.gray(`Executing in ${name}: ${command}`));

  try {
    const fullCommand = options.sudo 
      ? `multipass exec ${name} -- sudo ${command}`
      : `multipass exec ${name} -- ${command}`;

    const output = execSync(fullCommand, {
      stdio: 'inherit',
      timeout: parseInt(options.timeout)
    });

    return 0;

  } catch (error) {
    console.error(chalk.red('Command failed'));
    process.exit(error.status || 1);
  }
}

module.exports = execCommand;
