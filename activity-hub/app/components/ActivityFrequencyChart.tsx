'use client';

import { useEffect, useRef } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

interface ActivityFrequencyChartProps {
  activities: any[];
}

export default function ActivityFrequencyChart({ activities }: ActivityFrequencyChartProps) {
  const chartRef = useRef<ChartJS<'bar'>>(null);

  // Generate last 2 hours in 5-minute intervals (24 intervals)
  const generateTimeIntervals = () => {
    const intervals: string[] = [];
    const now = new Date();
    
    for (let i = 23; i >= 0; i--) {
      const time = new Date(now.getTime() - i * 5 * 60 * 1000);
      const hours = time.getHours();
      const minutes = time.getMinutes();
      intervals.push(`${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`);
    }
    
    return intervals;
  };

  // Bucket activities into 5-minute intervals
  const bucketActivities = () => {
    const now = Date.now();
    const twoHoursAgo = now - 2 * 60 * 60 * 1000;
    const intervals = generateTimeIntervals();
    
    // Initialize buckets for each category
    const buckets: Record<string, Record<string, number>> = {};
    
    intervals.forEach(interval => {
      buckets[interval] = {
        'file-create': 0,
        'file-edit': 0,
        'file-read': 0,
        'command': 0,
        'system': 0
      };
    });
    
    // Filter activities from last 2 hours and bucket them
    activities
      .filter(act => act.timestamp >= twoHoursAgo)
      .forEach(act => {
        const actTime = new Date(act.timestamp);
        const hours = actTime.getHours();
        const minutes = Math.floor(actTime.getMinutes() / 5) * 5; // Round down to 5-min interval
        const intervalKey = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
        
        if (buckets[intervalKey]) {
          const category = act.metadata?.category || 'system';
          if (buckets[intervalKey][category] !== undefined) {
            buckets[intervalKey][category]++;
          }
        }
      });
    
    return { intervals, buckets };
  };

  const { intervals, buckets } = bucketActivities();

  // Prepare chart data
  const data = {
    labels: intervals,
    datasets: [
      {
        label: 'File Creates',
        data: intervals.map(interval => buckets[interval]['file-create']),
        backgroundColor: '#00ff88',
        borderColor: '#00ff88',
        borderWidth: 0,
      },
      {
        label: 'File Edits',
        data: intervals.map(interval => buckets[interval]['file-edit']),
        backgroundColor: '#00d9ff',
        borderColor: '#00d9ff',
        borderWidth: 0,
      },
      {
        label: 'File Reads',
        data: intervals.map(interval => buckets[interval]['file-read']),
        backgroundColor: '#888',
        borderColor: '#888',
        borderWidth: 0,
      },
      {
        label: 'Commands',
        data: intervals.map(interval => buckets[interval]['command']),
        backgroundColor: '#9b59b6',
        borderColor: '#9b59b6',
        borderWidth: 0,
      },
      {
        label: 'System',
        data: intervals.map(interval => buckets[interval]['system']),
        backgroundColor: '#feca57',
        borderColor: '#feca57',
        borderWidth: 0,
      },
    ],
  };

  const options: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        stacked: true,
        grid: {
          color: 'rgba(255, 255, 255, 0.05)',
        },
        ticks: {
          color: '#888',
          maxRotation: 45,
          minRotation: 45,
          font: {
            size: 10,
          },
        },
        title: {
          display: true,
          text: 'Time (Last 2 Hours)',
          color: '#888',
          font: {
            size: 12,
            weight: 'normal',
          },
        },
      },
      y: {
        stacked: true,
        grid: {
          color: 'rgba(255, 255, 255, 0.05)',
        },
        ticks: {
          color: '#888',
          stepSize: 1,
          font: {
            size: 11,
          },
        },
        title: {
          display: true,
          text: 'Number of Activities',
          color: '#888',
          font: {
            size: 12,
            weight: 'normal',
          },
        },
        beginAtZero: true,
      },
    },
    plugins: {
      legend: {
        display: true,
        position: 'top',
        labels: {
          color: '#ccc',
          font: {
            size: 12,
          },
          padding: 15,
          usePointStyle: true,
          pointStyle: 'rect',
        },
      },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.9)',
        titleColor: '#fff',
        bodyColor: '#ccc',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderWidth: 1,
        padding: 12,
        displayColors: true,
        callbacks: {
          title: (context) => {
            return `Time: ${context[0].label}`;
          },
          label: (context) => {
            const label = context.dataset.label || '';
            const value = context.parsed.y;
            return value > 0 ? `${label}: ${value}` : '';
          },
          footer: (context) => {
            const total = context.reduce((sum, item) => sum + item.parsed.y, 0);
            return total > 0 ? `\nTotal: ${total} activities` : '';
          },
        },
      },
    },
    interaction: {
      mode: 'index',
      intersect: false,
    },
  };

  // Calculate total activities in view
  const totalInView = Object.values(buckets).reduce((sum, bucket) => {
    return sum + Object.values(bucket).reduce((s, v) => s + v, 0);
  }, 0);

  return (
    <div className="bg-white/5 border border-gray-800 rounded-lg p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Activity Frequency</h3>
          <p className="text-sm text-gray-400 mt-1">
            Last 2 hours • 5-minute intervals
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-[#00d9ff]">{totalInView}</div>
          <div className="text-xs text-gray-500">activities in period</div>
        </div>
      </div>
      
      <div style={{ height: '300px' }}>
        <Bar ref={chartRef} data={data} options={options} />
      </div>
      
      {totalInView === 0 && (
        <div className="mt-4 text-center text-gray-500 text-sm">
          No activities in the last 2 hours. Start working with sub-agents to see activity patterns!
        </div>
      )}
    </div>
  );
}
