const { execSync } = require('child_process');
const http = require('http');
const chalk = require('chalk');
const ora = require('ora');
const readline = require('readline');

async function destroyCommand(name, options) {
  if (!options.force) {
    const answer = await ask(`Are you sure you want to destroy agent ${name}? (y/N) `);
    if (answer.toLowerCase() !== 'y') {
      console.log(chalk.yellow('Aborted'));
      return;
    }
  }

  const spinner = ora('Destroying agent...').start();

  try {
    // Deregister from hub
    try {
      await httpDelete(`http://localhost:9091/agents/${name}`);
      spinner.text = 'Deregistered from hub';
    } catch (error) {
      spinner.warn('Failed to deregister from hub (continuing)');
    }

    // Delete VM
    try {
      execSync(`multipass delete ${name}`, { stdio: 'pipe' });
      execSync(`multipass purge`, { stdio: 'pipe' });
      spinner.succeed(chalk.green(`Agent ${name} destroyed successfully`));
    } catch (error) {
      spinner.fail(chalk.red('Failed to delete VM'));
      throw error;
    }

  } catch (error) {
    spinner.fail(chalk.red('Failed to destroy agent'));
    console.error(chalk.red('Error:'), error.message);
    process.exit(1);
  }
}

function ask(question) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  return new Promise(resolve => {
    rl.question(question, answer => {
      rl.close();
      resolve(answer);
    });
  });
}

function httpDelete(url) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port,
      path: urlObj.pathname,
      method: 'DELETE'
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(JSON.parse(data));
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${data}`));
        }
      });
    });

    req.on('error', reject);
    req.end();
  });
}

module.exports = destroyCommand;
