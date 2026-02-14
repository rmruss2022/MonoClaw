function calculateEntropy(charsetSize, length) {
  // Entropy (bits) = log2(charset_size ^ length)
  // = length * log2(charset_size)
  return Math.floor(length * Math.log2(charsetSize));
}

function getEntropyStrength(entropyBits) {
  if (entropyBits < 50) return 'weak';
  if (entropyBits < 80) return 'moderate';
  return 'strong';
}

function getEntropyDescription(entropyBits) {
  if (entropyBits < 40) return 'Very Weak - Easily crackable';
  if (entropyBits < 50) return 'Weak - Consider longer password';
  if (entropyBits < 60) return 'Moderate - Acceptable for low-security';
  if (entropyBits < 80) return 'Good - Suitable for most uses';
  if (entropyBits < 100) return 'Strong - Excellent security';
  return 'Very Strong - Maximum security';
}

module.exports = {
  calculateEntropy,
  getEntropyStrength,
  getEntropyDescription
};
