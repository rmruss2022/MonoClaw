#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const PROFILES_DIR = path.join(__dirname, '../../profiles');

function listProfiles() {
  console.log('\n📋 Available Agent Profiles:\n');
  
  const files = fs.readdirSync(PROFILES_DIR)
    .filter(f => f.endsWith('.json'));
  
  if (files.length === 0) {
    console.log('No profiles found.');
    return;
  }
  
  files.forEach(file => {
    const profilePath = path.join(PROFILES_DIR, file);
    const profile = JSON.parse(fs.readFileSync(profilePath, 'utf8'));
    
    console.log(`🔹 ${profile.name}`);
    console.log(`   ${profile.description}`);
    console.log(`   Resources: ${profile.resources.cpu} CPU, ${profile.resources.memory} RAM, ${profile.resources.disk} disk`);
    console.log(`   Tools: ${profile.packages?.join(', ') || 'standard'}`);
    console.log('');
  });
}

function showProfile(name) {
  const profilePath = path.join(PROFILES_DIR, `${name}.json`);
  
  if (!fs.existsSync(profilePath)) {
    console.error(`❌ Profile '${name}' not found.`);
    process.exit(1);
  }
  
  const profile = JSON.parse(fs.readFileSync(profilePath, 'utf8'));
  
  console.log(`\n📦 Profile: ${profile.name}\n`);
  console.log(`Description: ${profile.description}\n`);
  
  console.log('Resources:');
  console.log(`  CPU: ${profile.resources.cpu}`);
  console.log(`  Memory: ${profile.resources.memory}`);
  console.log(`  Disk: ${profile.resources.disk}\n`);
  
  if (profile.environment && Object.keys(profile.environment).length > 0) {
    console.log('Environment Variables:');
    Object.entries(profile.environment).forEach(([key, value]) => {
      console.log(`  ${key}=${value}`);
    });
    console.log('');
  }
  
  if (profile.packages && profile.packages.length > 0) {
    console.log('System Packages:');
    profile.packages.forEach(pkg => console.log(`  - ${pkg}`));
    console.log('');
  }
  
  if (profile.files && profile.files.length > 0) {
    console.log('Files to Create:');
    profile.files.forEach(file => {
      console.log(`  - ${file.path}`);
    });
    console.log('');
  }
  
  if (profile.setup_tasks && profile.setup_tasks.length > 0) {
    console.log('Setup Tasks:');
    profile.setup_tasks.forEach((task, i) => {
      console.log(`  ${i + 1}. ${task.description || task.command}`);
    });
    console.log('');
  }
}

function createProfile(name, options) {
  const profilePath = path.join(PROFILES_DIR, `${name}.json`);
  
  if (fs.existsSync(profilePath) && !options.force) {
    console.error(`❌ Profile '${name}' already exists. Use --force to overwrite.`);
    process.exit(1);
  }
  
  let profile;
  
  if (options.fromFile) {
    if (!fs.existsSync(options.fromFile)) {
      console.error(`❌ File '${options.fromFile}' not found.`);
      process.exit(1);
    }
    profile = JSON.parse(fs.readFileSync(options.fromFile, 'utf8'));
    profile.name = name;
  } else {
    // Interactive creation
    profile = {
      name,
      description: options.description || 'Custom agent profile',
      resources: {
        cpu: parseInt(options.cpu) || 2,
        memory: options.memory || '4G',
        disk: options.disk || '20G'
      },
      environment: {},
      files: [],
      packages: [],
      setup_tasks: []
    };
  }
  
  fs.writeFileSync(profilePath, JSON.stringify(profile, null, 2));
  console.log(`✅ Profile '${name}' created at ${profilePath}`);
}

function deleteProfile(name, options) {
  const profilePath = path.join(PROFILES_DIR, `${name}.json`);
  
  if (!fs.existsSync(profilePath)) {
    console.error(`❌ Profile '${name}' not found.`);
    process.exit(1);
  }
  
  if (!options.force) {
    console.log(`⚠️  Are you sure you want to delete profile '${name}'?`);
    console.log('Use --force to confirm deletion.');
    process.exit(1);
  }
  
  fs.unlinkSync(profilePath);
  console.log(`✅ Profile '${name}' deleted.`);
}

function loadProfile(name) {
  const profilePath = path.join(PROFILES_DIR, `${name}.json`);
  
  if (!fs.existsSync(profilePath)) {
    throw new Error(`Profile '${name}' not found`);
  }
  
  return JSON.parse(fs.readFileSync(profilePath, 'utf8'));
}

module.exports = {
  listProfiles,
  showProfile,
  createProfile,
  deleteProfile,
  loadProfile
};

// CLI execution
if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];
  
  switch (command) {
    case 'list':
      listProfiles();
      break;
      
    case 'show':
      if (!args[1]) {
        console.error('Usage: profiles show <name>');
        process.exit(1);
      }
      showProfile(args[1]);
      break;
      
    case 'create':
      if (!args[1]) {
        console.error('Usage: profiles create <name> [options]');
        process.exit(1);
      }
      const createOptions = {
        fromFile: args.includes('--from-file') ? args[args.indexOf('--from-file') + 1] : null,
        force: args.includes('--force'),
        description: args.includes('--description') ? args[args.indexOf('--description') + 1] : null,
        cpu: args.includes('--cpu') ? args[args.indexOf('--cpu') + 1] : null,
        memory: args.includes('--memory') ? args[args.indexOf('--memory') + 1] : null,
        disk: args.includes('--disk') ? args[args.indexOf('--disk') + 1] : null
      };
      createProfile(args[1], createOptions);
      break;
      
    case 'delete':
      if (!args[1]) {
        console.error('Usage: profiles delete <name> --force');
        process.exit(1);
      }
      const deleteOptions = {
        force: args.includes('--force')
      };
      deleteProfile(args[1], deleteOptions);
      break;
      
    default:
      console.log('Usage: profiles <command> [options]');
      console.log('');
      console.log('Commands:');
      console.log('  list              List all available profiles');
      console.log('  show <name>       Show profile details');
      console.log('  create <name>     Create new profile');
      console.log('  delete <name>     Delete profile');
      break;
  }
}
