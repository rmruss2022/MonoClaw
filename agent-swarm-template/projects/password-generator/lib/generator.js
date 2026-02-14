const crypto = require('crypto');

const CHARSETS = {
  lowercase: 'abcdefghijklmnopqrstuvwxyz',
  uppercase: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
  numbers: '0123456789',
  special: '!@#$%^&*()_+-=[]{}|;:,.<>?'
};

function generatePassword(options = {}) {
  const {
    length = 16,
    lowercase = true,
    uppercase = true,
    numbers = true,
    special = true
  } = options;

  // Build character set
  let charset = '';
  if (lowercase) charset += CHARSETS.lowercase;
  if (uppercase) charset += CHARSETS.uppercase;
  if (numbers) charset += CHARSETS.numbers;
  if (special) charset += CHARSETS.special;

  if (charset.length === 0) {
    throw new Error('At least one character set must be enabled');
  }

  if (length < 8 || length > 128) {
    throw new Error('Password length must be between 8 and 128');
  }

  // Generate password using crypto.randomBytes
  const password = [];
  const randomBytes = crypto.randomBytes(length);

  for (let i = 0; i < length; i++) {
    const randomIndex = randomBytes[i] % charset.length;
    password.push(charset[randomIndex]);
  }

  return {
    password: password.join(''),
    charsetSize: charset.length,
    length: length
  };
}

module.exports = { generatePassword, CHARSETS };
