const os = require('os');
const fs = require('fs').promises;
const { exec } = require('child_process');
const { promisify } = require('util');

const execPromise = promisify(exec);

class HealthMonitor {
  constructor(client) {
    this.client = client;
    this.interval = 30000; // 30 seconds
    this.timer = null;
    this.startTime = Date.now();
  }

  /**
   * Start health monitoring
   */
  start() {
    console.log('[HEALTH] Starting health monitor');
    
    // Send initial health check
    this.sendHealthCheck();

    // Set up periodic health checks
    this.timer = setInterval(() => {
      this.sendHealthCheck();
    }, this.interval);
  }

  /**
   * Stop health monitoring
   */
  stop() {
    console.log('[HEALTH] Stopping health monitor');
    
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  /**
   * Send health check to hub
   */
  async sendHealthCheck() {
    try {
      const health = await this.collectHealthData();
      
      this.client.sendMessage({
        type: 'health',
        payload: health
      });

    } catch (error) {
      console.error('[HEALTH] Failed to collect health data:', error);
    }
  }

  /**
   * Collect health data
   * @returns {Promise<object>} Health data
   */
  async collectHealthData() {
    const [cpu, memory, disk] = await Promise.all([
      this.getCpuUsage(),
      this.getMemoryUsage(),
      this.getDiskUsage()
    ]);

    return {
      cpu,
      memory,
      disk,
      uptime: Math.floor((Date.now() - this.startTime) / 1000),
      systemUptime: Math.floor(os.uptime()),
      loadAverage: os.loadavg(),
      platform: os.platform(),
      arch: os.arch(),
      hostname: os.hostname(),
      timestamp: Date.now()
    };
  }

  /**
   * Get CPU usage percentage
   * @returns {Promise<number>} CPU usage (0-100)
   */
  async getCpuUsage() {
    const cpus = os.cpus();
    
    let totalIdle = 0;
    let totalTick = 0;

    cpus.forEach(cpu => {
      for (let type in cpu.times) {
        totalTick += cpu.times[type];
      }
      totalIdle += cpu.times.idle;
    });

    const idle = totalIdle / cpus.length;
    const total = totalTick / cpus.length;
    const usage = 100 - ~~(100 * idle / total);

    return Math.round(usage * 100) / 100;
  }

  /**
   * Get memory usage
   * @returns {object} Memory usage data
   */
  getMemoryUsage() {
    const total = os.totalmem();
    const free = os.freemem();
    const used = total - free;
    const usagePercent = (used / total) * 100;

    return {
      total: Math.round(total / 1024 / 1024), // MB
      used: Math.round(used / 1024 / 1024), // MB
      free: Math.round(free / 1024 / 1024), // MB
      usagePercent: Math.round(usagePercent * 100) / 100
    };
  }

  /**
   * Get disk usage
   * @returns {Promise<object>} Disk usage data
   */
  async getDiskUsage() {
    try {
      const platform = os.platform();
      let command;

      if (platform === 'linux') {
        command = "df -k / | tail -1 | awk '{print $2,$3,$4,$5}'";
      } else if (platform === 'darwin') {
        command = "df -k / | tail -1 | awk '{print $2,$3,$4,$5}'";
      } else {
        // Windows or unsupported platform
        return {
          total: 0,
          used: 0,
          free: 0,
          usagePercent: 0
        };
      }

      const { stdout } = await execPromise(command);
      const [total, used, free, percent] = stdout.trim().split(/\s+/);

      return {
        total: Math.round(parseInt(total) / 1024), // MB
        used: Math.round(parseInt(used) / 1024), // MB
        free: Math.round(parseInt(free) / 1024), // MB
        usagePercent: parseFloat(percent.replace('%', ''))
      };
    } catch (error) {
      console.error('[HEALTH] Failed to get disk usage:', error);
      return {
        total: 0,
        used: 0,
        free: 0,
        usagePercent: 0
      };
    }
  }

  /**
   * Get network stats (optional)
   * @returns {Promise<object>} Network stats
   */
  async getNetworkStats() {
    const interfaces = os.networkInterfaces();
    const stats = {};

    for (const [name, addrs] of Object.entries(interfaces)) {
      const ipv4 = addrs.find(addr => addr.family === 'IPv4');
      if (ipv4) {
        stats[name] = {
          address: ipv4.address,
          netmask: ipv4.netmask,
          mac: ipv4.mac
        };
      }
    }

    return stats;
  }
}

module.exports = HealthMonitor;
