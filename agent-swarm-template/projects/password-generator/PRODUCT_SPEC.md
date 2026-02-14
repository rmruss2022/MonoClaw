# Password Generator CLI - Product Specification

## Overview

A secure, fast, and feature-rich command-line tool for generating strong passwords with customizable entropy and character sets.

---

## 1. CLI Interface and Commands

### Command Structure
```
passgen [options]
passgen <command> [options]
```

### Commands

| Command | Description |
|---------|-------------|
| `generate` | Generate password(s) - default command |
| `check` | Check password strength/entropy |
| `config` | Manage default settings |
| `version` | Show version information |
| `help` | Display help information |

### Examples
```bash
# Quick password generation
passgen
passgen -l 32
passgen -l 16 --no-symbols

# Multiple passwords
passgen -n 10 -l 20

# Check existing password
passgen check "MyP@ssw0rd!"

# Config management
passgen config set default-length 24
passgen config get
```

---

## 2. Password Generation Options

### Length Options
- **Default:** 16 characters
- **Range:** 8 - 256 characters
- **CLI flags:** `-l, --length <n>`

### Character Set Options

| Flag | Description | Included Characters | Default |
|------|-------------|---------------------|---------|
| `--lowercase` | Lowercase letters | a-z | ✓ |
| `--uppercase` | Uppercase letters | A-Z | ✓ |
| `--numbers` | Digits | 0-9 | ✓ |
| `--symbols` | Special symbols | `!@#$%^&*()_+-=[]{}|;:,.<>?` | ✓ |
| `--ambiguous` | Ambiguous characters | `0OIl1|` | ✓ (excluded) |
| `--spaces` | Include spaces | ` ` | ✗ |

### Quantity Options
- **Flag:** `-n, --count <n>`
- **Range:** 1 - 100 passwords per run
- **Default:** 1

### Generation Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `random` | Fully random characters | General purpose |
| `memorable` | XKCD-style passphrases | Human-memorable |
| `pin` | Numeric only | Simple PINs |
| `secure` | Maximum entropy (256-bit) | Maximum security |

### Memorable Mode Options (XKCD-style)
- **Word count:** 4-8 words (default: 4)
- **Separator:** `-`, `_`, ` `, or random (default: `-`)
- **Word list:** 50,000+ English words
- **Entropy per word:** ~12.3 bits

---

## 3. Security Considerations

### Entropy Calculation

The tool calculates and reports entropy for all generated passwords:

```
Entropy Formula: H = L × log₂(R)

Where:
- H = Entropy in bits
- L = Password length
- R = Size of character pool
```

| Entropy Range | Strength | Use Case |
|---------------|----------|----------|
| < 40 bits | Weak | Low security, temporary |
| 40-60 bits | Moderate | Basic applications |
| 60-80 bits | Strong | Most online services |
| 80-128 bits | Very Strong | Financial/sensitive |
| > 128 bits | Maximum | Military/cryptographic |

### Security Requirements

1. **Cryptographically Secure Random Number Generator**
   - Use OS-native CSPRNG (`/dev/urandom`, `CryptGenRandom`, etc.)
   - Never use pseudo-random generators

2. **No Logging**
   - Passwords must never be logged to disk
   - No clipboard history pollution
   - Session memory cleared after use

3. **Clipboard Security**
   - Auto-clear clipboard after configurable timeout (default: 30s)
   - Preserve clipboard history (optional)
   - Support for multiple clipboard formats

4. **Character Distribution**
   - Ensure uniform distribution across character sets
   - Guarantee at least one character from each enabled set
   - Prevent patterns or biases

---

## 4. Output Formats and User Experience

### Output Formats

| Format | Flag | Description |
|--------|------|-------------|
| `plain` | `--format plain` | Simple password list |
| `table` | `--format table` | Formatted table with details |
| `json` | `--format json` | JSON output (pipeable) |
| `csv` | `--format csv` | CSV format |

### Default Table Output Example
```
┌──────────────────────────────────┬──────────┬──────────┬──────────┐
│ Password                         │ Length   │ Entropy  │ Strength │
├──────────────────────────────────┼──────────┼──────────┼──────────┤
│ Zx9#mK2$pL8!vQwRd                │ 16       │ 95.6 bit │ Strong   │
└──────────────────────────────────┴──────────┴──────────┴──────────┘
```

### Copy to Clipboard
- **Flag:** `--copy` or `-c`
- **Default timeout:** 30 seconds before auto-clear
- **Confirmation:** "Password copied to clipboard (clears in 30s)"

### Configuration File
- **Location:** `~/.config/passgen/config.toml` (Linux/Mac)
- **Location (Windows):** `%APPDATA%\passgen\config.toml`

```toml
[defaults]
length = 16
count = 1
numbers = true
symbols = true
lowercase = true
uppercase = true
ambiguous = false
spaces = false
format = "table"
clipboard_timeout = 30

[mode.memorable]
words = 4
separator = "-"
capitalize = true
```

---

## 5. Success Criteria and Acceptance Tests

### Functional Requirements

| ID | Requirement | Test |
|----|-------------|------|
| F1 | Generate password with default settings | Run `passgen` and verify 16-char password |
| F2 | Custom length generation | Run `passgen -l 32` and verify length |
| F3 | Character set exclusion | Run `passgen --no-symbols` and verify no symbols |
| F4 | Multiple passwords | Run `passgen -n 5` and verify count |
| F5 | Memorable mode | Run `passgen --mode memorable` and verify words |
| F6 | PIN mode | Run `passgen --mode pin` and verify digits only |
| F7 | JSON output | Run `passgen --format json` and parse valid JSON |
| F8 | Copy to clipboard | Run `passgen --copy` and verify clipboard |
| F9 | Password strength check | Run `passgen check "password"` and verify output |
| F10 | Config persistence | Set/get config and verify persistence |

### Security Requirements

| ID | Requirement | Test |
|----|-------------|------|
| S1 | Minimum entropy 60 bits for default config | Verify entropy calculation |
| S2 | CSPRNG usage | Code review and entropy testing |
| S3 | No password logging | Audit file system operations |
| S4 | Clipboard auto-clear | Verify timeout behavior |
| S5 | Memory clearing | Verify sensitive data wiped |
| S6 | No hardcoded defaults | Verify all defaults in config |

### Performance Requirements

| ID | Requirement | Test |
|----|-------------|------|
| P1 | Generate 100 passwords in < 100ms | Benchmark test |
| P2 | Startup time < 50ms | Time `passgen --help` |
| P3 | Memory usage < 10MB | Memory profiling |

### Edge Cases

| Case | Expected Behavior |
|------|-----------------|
| Length 0 | Error: "Length must be at least 8" |
| Length > 256 | Error: "Length cannot exceed 256" |
| All character sets disabled | Error: "At least one character set required" |
| Invalid mode | Error: "Unknown mode: X. Valid modes: random, memorable, pin" |
| Clipboard unavailable | Warning + proceed with terminal output |

---

## 6. Implementation Notes

### Recommended Stack
- Primary: Rust (for performance + safety)
- Alternative: Python with `secrets` module
- Alternative: Go with `crypto/rand`

### Dependencies
- Secure random: OS-native CSPRNG
- Clipboard: `clipboard` crate (Rust) or `clipboardy` (Node)
- CLI: `clap` (Rust) or `argparse` (Python)

### Build Targets
- Linux (x86_64, ARM64)
- macOS (x86_64, Apple Silicon)
- Windows (x86_64)

---

## 7. Future Enhancements (Out of Scope)

- [ ] Password history
- [ ] Custom word lists
- [ ] Integration with password managers
- [ ] TOTP generation
- [ ] Password sharing via secure hash
- [ ] Themed passwords

---

**Version:** 1.0.0
**Last Updated:** 2026-02-12
**Author:** Product-Spec-Agent
**Status:** Draft → Ready for Implementation
