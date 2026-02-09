import { useState, useEffect } from 'react';

// Server-side data fetching for initial load
export async function getServerSideProps() {
  const fs = await import('fs');
  const path = await import('path');
  
  const reportsDir = path.join(process.env.HOME || '/tmp', '.openclaw/workspace/skill-builder/reports');
  const skillsDir = path.join(process.env.HOME || '/tmp', '.openclaw/workspace/skills');
  
  let latestReport = null;
  
  try {
    const latestPath = path.join(reportsDir, 'latest.json');
    if (fs.existsSync(latestPath)) {
      latestReport = JSON.parse(fs.readFileSync(latestPath, 'utf8'));
    }
  } catch (e) {
    console.error('Failed to load report:', e);
  }
  
  return {
    props: {
      latestReport
    }
  };
}

export default function Dashboard({ latestReport }) {
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(latestReport);
  
  const refresh = async () => {
    setLoading(true);
    try {
      // In a real app, this would fetch from an API
      // For now, reload the page to get fresh data
      window.location.reload();
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>🔍 Skill Builder Dashboard</h1>
        <button onClick={refresh} disabled={loading} style={styles.button}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </header>
      
      {report && (
        <div style={styles.grid}>
          {/* Summary Cards */}
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>Services</h3>
            <div style={styles.bigNumber}>{report.summary.totalDiscovered}</div>
            <div style={styles.breakdown}>
              <span style={styles.running}>● {report.summary.running} running</span>
              <span style={styles.stopped}>● {report.summary.stopped} stopped</span>
            </div>
          </div>
          
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>Skills Created</h3>
            <div style={styles.bigNumber}>{report.summary.skillsCreated}</div>
            <div style={styles.breakdown}>
              <span>Last run: {new Date(report.timestamp).toLocaleString()}</span>
            </div>
          </div>
          
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>Latest Run</h3>
            <div style={{fontSize: '14px', marginTop: '8px'}}>
              <div><strong>ID:</strong> {report.runId}</div>
              <div><strong>Time:</strong> {new Date(report.timestamp).toLocaleTimeString()}</div>
              <div><strong>Errors:</strong> {report.errors.length}</div>
            </div>
          </div>
        </div>
      )}
      
      {/* Services List */}
      <div style={styles.tableContainer}>
        <h2 style={styles.sectionTitle}>Discovered Services</h2>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Name</th>
              <th style={styles.th}>Type</th>
              <th style={styles.th}>Port</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Skill</th>
            </tr>
          </thead>
          <tbody>
            {report?.discovered.map((service) => (
              <tr key={service.name} style={styles.tr}>
                <td style={styles.td}>{service.name}</td>
                <td style={styles.td}>
                  <span style={styles.badge}>{service.type}</span>
                </td>
                <td style={styles.td}>{service.port || '-'}</td>
                <td style={styles.td}>
                  <span style={service.status === 'running' ? styles.statusRunning : styles.statusStopped}>
                    {service.status}
                  </span>
                </td>
                <td style={styles.td}>
                  {service.skillCreated ? 
                    <span style={styles.success}>✓ Created</span> : 
                    <span style={styles.error}>✗ Failed</span>
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {/* Footer */}
      <footer style={styles.footer}>
        <p>Skill Builder v1.0 • Port 18798 • <a href="/api/runs">View All Runs</a></p>
      </footer>
    </div>
  );
}

const styles = {
  container: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '20px',
    fontFamily: 'system-ui, -apple-system, sans-serif'
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '24px',
    paddingBottom: '16px',
    borderBottom: '1px solid #e5e7eb'
  },
  title: {
    margin: 0,
    fontSize: '24px'
  },
  button: {
    padding: '8px 16px',
    borderRadius: '6px',
    border: '1px solid #d1d5db',
    background: '#fff',
    cursor: 'pointer',
    fontSize: '14px'
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
    gap: '16px',
    marginBottom: '24px'
  },
  card: {
    padding: '20px',
    borderRadius: '8px',
    border: '1px solid #e5e7eb',
    background: '#fff'
  },
  cardTitle: {
    margin: '0 0 12px 0',
    fontSize: '14px',
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: '0.5px'
  },
  bigNumber: {
    fontSize: '36px',
    fontWeight: 'bold',
    color: '#111827'
  },
  breakdown: {
    marginTop: '8px',
    fontSize: '14px',
    color: '#6b7280'
  },
  running: { color: '#22c55e' },
  stopped: { color: '#9ca3af' },
  tableContainer: {
    background: '#fff',
    borderRadius: '8px',
    border: '1px solid #e5e7eb',
    overflow: 'hidden'
  },
  sectionTitle: {
    margin: 0,
    padding: '16px 20px',
    borderBottom: '1px solid #e5e7eb',
    fontSize: '18px'
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse'
  },
  th: {
    textAlign: 'left',
    padding: '12px 20px',
    fontSize: '12px',
    fontWeight: '600',
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    borderBottom: '1px solid #e5e7eb'
  },
  tr: {
    borderBottom: '1px solid #e5e7eb'
  },
  td: {
    padding: '12px 20px',
    fontSize: '14px'
  },
  badge: {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: '12px',
    background: '#e0e7ff',
    color: '#4338ca',
    fontSize: '12px',
    fontWeight: '500'
  },
  statusRunning: {
    color: '#22c55e',
    fontWeight: '500'
  },
  statusStopped: {
    color: '#9ca3af'
  },
  success: {
    color: '#22c55e'
  },
  error: {
    color: '#ef4444'
  },
  footer: {
    marginTop: '32px',
    paddingTop: '16px',
    borderTop: '1px solid #e5e7eb',
    textAlign: 'center',
    color: '#6b7280',
    fontSize: '14px'
  }
};
