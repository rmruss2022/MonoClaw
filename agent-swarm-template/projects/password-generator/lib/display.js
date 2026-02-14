const chalk = require('chalk');
const { calculateEntropy, getEntropyStrength, getEntropyDescription } = require('./entropy');

function displayPassword(result, options = {}) {
  const { showEntropy = false } = options;
  const { password, charsetSize, length } = result;

  console.log(chalk.bold('\n🔐 Generated Password:'));
  console.log(chalk.cyan(password));

  if (showEntropy) {
    const entropy = calculateEntropy(charsetSize, length);
    const strength = getEntropyStrength(entropy);
    const description = getEntropyDescription(entropy);

    console.log(chalk.bold('\n📊 Security Analysis:'));
    console.log(`  Charset size: ${charsetSize} characters`);
    console.log(`  Length: ${length} characters`);
    console.log(`  Entropy: ${entropy} bits`);
    
    const strengthColor = strength === 'weak' ? chalk.red : strength === 'moderate' ? chalk.yellow : chalk.green;
    console.log(`  Strength: ${strengthColor.bold(strength.toUpperCase())}`);
    console.log(`  ${description}`);
    
    // Visual entropy bar
    const barLength = 40;
    const filledLength = Math.min(Math.floor((entropy / 128) * barLength), barLength);
    const bar = '█'.repeat(filledLength) + '░'.repeat(barLength - filledLength);
    console.log(`  ${strengthColor(bar)} ${entropy}/128 bits\n`);
  } else {
    console.log('');
  }
}

function displayMultiplePasswords(passwords, showEntropy = false) {
  console.log(chalk.bold(`\n🔐 Generated ${passwords.length} Passwords:\n`));
  passwords.forEach((result, index) => {
    console.log(chalk.gray(`${index + 1}.`), chalk.cyan(result.password));
  });
  
  if (showEntropy && passwords.length > 0) {
    const entropy = calculateEntropy(passwords[0].charsetSize, passwords[0].length);
    const strength = getEntropyStrength(entropy);
    const strengthColor = strength === 'weak' ? chalk.red : strength === 'moderate' ? chalk.yellow : chalk.green;
    console.log(chalk.gray(`\n   Entropy: ${entropy} bits (${strengthColor(strength)})\n`));
  } else {
    console.log('');
  }
}

module.exports = {
  displayPassword,
  displayMultiplePasswords
};
