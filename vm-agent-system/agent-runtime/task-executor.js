const { spawn, exec } = require('child_process');
const fs = require('fs').promises;
const path = require('path');
const { promisify } = require('util');

const execPromise = promisify(exec);

class TaskExecutor {
  constructor() {
    this.activeTasks = new Map();
    this.defaultTimeout = 30 * 60 * 1000; // 30 minutes
  }

  /**
   * Execute a task
   * @param {object} task - Task to execute
   * @returns {Promise<object>} Task result
   */
  async execute(task) {
    const taskId = task.taskId || task.id;
    const startTime = Date.now();

    console.log(`[EXECUTOR] Starting task ${taskId}: ${task.type}`);

    try {
      let result;

      switch (task.type) {
        case 'exec':
          result = await this.executeCommand(task);
          break;

        case 'script':
          result = await this.executeScript(task);
          break;

        case 'file:read':
          result = await this.readFile(task);
          break;

        case 'file:write':
          result = await this.writeFile(task);
          break;

        case 'git:clone':
          result = await this.gitClone(task);
          break;

        case 'git:pull':
          result = await this.gitPull(task);
          break;

        case 'git:push':
          result = await this.gitPush(task);
          break;

        case 'build':
          result = await this.runBuild(task);
          break;

        case 'test':
          result = await this.runTests(task);
          break;

        case 'deploy':
          result = await this.runDeploy(task);
          break;

        default:
          throw new Error(`Unknown task type: ${task.type}`);
      }

      const duration = Date.now() - startTime;

      console.log(`[EXECUTOR] Task ${taskId} completed in ${duration}ms`);

      return {
        taskId,
        success: true,
        result,
        duration,
        timestamp: Date.now()
      };

    } catch (error) {
      const duration = Date.now() - startTime;

      console.error(`[EXECUTOR] Task ${taskId} failed:`, error.message);

      return {
        taskId,
        success: false,
        error: error.message,
        stack: error.stack,
        duration,
        timestamp: Date.now()
      };
    } finally {
      this.activeTasks.delete(taskId);
    }
  }

  /**
   * Execute a shell command
   * @param {object} task - Task with command
   * @returns {Promise<object>} Execution result
   */
  async executeCommand(task) {
    const { command, cwd, env, timeout, sudo } = task;

    if (sudo && !task.allowSudo) {
      throw new Error('Sudo execution requires allowSudo flag');
    }

    const finalCommand = sudo ? `sudo ${command}` : command;
    const timeoutMs = timeout || this.defaultTimeout;

    const { stdout, stderr } = await execPromise(finalCommand, {
      cwd: cwd || process.cwd(),
      env: { ...process.env, ...env },
      timeout: timeoutMs,
      maxBuffer: 10 * 1024 * 1024 // 10MB
    });

    return {
      stdout: stdout.trim(),
      stderr: stderr.trim(),
      exitCode: 0
    };
  }

  /**
   * Execute a Node.js script
   * @param {object} task - Task with script
   * @returns {Promise<object>} Execution result
   */
  async executeScript(task) {
    const { script, args, cwd } = task;

    // Write script to temp file
    const tempFile = path.join('/tmp', `script-${Date.now()}.js`);
    await fs.writeFile(tempFile, script);

    try {
      const { stdout, stderr } = await execPromise(
        `node ${tempFile} ${args ? args.join(' ') : ''}`,
        {
          cwd: cwd || process.cwd(),
          timeout: task.timeout || this.defaultTimeout,
          maxBuffer: 10 * 1024 * 1024
        }
      );

      return {
        stdout: stdout.trim(),
        stderr: stderr.trim(),
        exitCode: 0
      };
    } finally {
      // Clean up temp file
      await fs.unlink(tempFile).catch(() => {});
    }
  }

  /**
   * Read a file
   * @param {object} task - Task with file path
   * @returns {Promise<object>} File content
   */
  async readFile(task) {
    const { filePath, encoding } = task;
    const content = await fs.readFile(filePath, encoding || 'utf8');

    return {
      filePath,
      content,
      size: Buffer.byteLength(content)
    };
  }

  /**
   * Write a file
   * @param {object} task - Task with file path and content
   * @returns {Promise<object>} Write result
   */
  async writeFile(task) {
    const { filePath, content, encoding } = task;

    // Create directory if it doesn't exist
    const dir = path.dirname(filePath);
    await fs.mkdir(dir, { recursive: true });

    await fs.writeFile(filePath, content, encoding || 'utf8');

    return {
      filePath,
      size: Buffer.byteLength(content)
    };
  }

  /**
   * Clone a git repository
   * @param {object} task - Task with repo URL
   * @returns {Promise<object>} Clone result
   */
  async gitClone(task) {
    const { repo, destination, branch } = task;

    const branchFlag = branch ? `-b ${branch}` : '';
    const command = `git clone ${branchFlag} ${repo} ${destination}`;

    const { stdout, stderr } = await execPromise(command, {
      timeout: task.timeout || this.defaultTimeout
    });

    return {
      repo,
      destination,
      branch: branch || 'default',
      stdout: stdout.trim(),
      stderr: stderr.trim()
    };
  }

  /**
   * Pull git changes
   * @param {object} task - Task with repo path
   * @returns {Promise<object>} Pull result
   */
  async gitPull(task) {
    const { repoPath } = task;

    const { stdout, stderr } = await execPromise('git pull', {
      cwd: repoPath,
      timeout: task.timeout || this.defaultTimeout
    });

    return {
      repoPath,
      stdout: stdout.trim(),
      stderr: stderr.trim()
    };
  }

  /**
   * Push git changes
   * @param {object} task - Task with repo path
   * @returns {Promise<object>} Push result
   */
  async gitPush(task) {
    const { repoPath, remote, branch } = task;

    const command = `git push ${remote || 'origin'} ${branch || 'main'}`;

    const { stdout, stderr } = await execPromise(command, {
      cwd: repoPath,
      timeout: task.timeout || this.defaultTimeout
    });

    return {
      repoPath,
      remote: remote || 'origin',
      branch: branch || 'main',
      stdout: stdout.trim(),
      stderr: stderr.trim()
    };
  }

  /**
   * Run build command
   * @param {object} task - Task with build command
   * @returns {Promise<object>} Build result
   */
  async runBuild(task) {
    const { command, cwd } = task;
    const buildCommand = command || 'npm run build';

    const { stdout, stderr } = await execPromise(buildCommand, {
      cwd: cwd || process.cwd(),
      timeout: task.timeout || this.defaultTimeout,
      maxBuffer: 10 * 1024 * 1024
    });

    return {
      command: buildCommand,
      stdout: stdout.trim(),
      stderr: stderr.trim(),
      exitCode: 0
    };
  }

  /**
   * Run tests
   * @param {object} task - Task with test command
   * @returns {Promise<object>} Test result
   */
  async runTests(task) {
    const { command, cwd } = task;
    const testCommand = command || 'npm test';

    const { stdout, stderr } = await execPromise(testCommand, {
      cwd: cwd || process.cwd(),
      timeout: task.timeout || this.defaultTimeout,
      maxBuffer: 10 * 1024 * 1024
    });

    return {
      command: testCommand,
      stdout: stdout.trim(),
      stderr: stderr.trim(),
      exitCode: 0
    };
  }

  /**
   * Run deployment
   * @param {object} task - Task with deploy command
   * @returns {Promise<object>} Deploy result
   */
  async runDeploy(task) {
    const { command, cwd } = task;

    if (!command) {
      throw new Error('Deploy task requires a command');
    }

    const { stdout, stderr } = await execPromise(command, {
      cwd: cwd || process.cwd(),
      timeout: task.timeout || this.defaultTimeout,
      maxBuffer: 10 * 1024 * 1024
    });

    return {
      command,
      stdout: stdout.trim(),
      stderr: stderr.trim(),
      exitCode: 0
    };
  }

  /**
   * Get active tasks
   * @returns {Array} Array of active task IDs
   */
  getActiveTasks() {
    return Array.from(this.activeTasks.keys());
  }
}

module.exports = TaskExecutor;
