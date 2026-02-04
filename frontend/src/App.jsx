import React, { useEffect, useMemo, useState } from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'
import { Bar } from 'react-chartjs-2'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

function formatDuration(seconds) {
  if (seconds == null) return '-'
  const s = Math.max(0, Number(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${sec}s`
  return `${sec}s`
}

export default function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/metrics/most-visited?hours=24')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setData(json)
    } catch (e) {
      setError(String(e?.message ?? e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const chart = useMemo(() => {
    const items = data?.items ?? []
    const labels = items.map((i) => i.zoneName || i.zoneId)
    const values = items.map((i) => i.totalSeconds)

    return {
      labels,
      datasets: [
        {
          label: 'Total time (seconds)',
          data: values,
          backgroundColor: 'rgba(59,130,246,0.7)',
          borderColor: 'rgba(59,130,246,1.0)',
          borderWidth: 1,
          borderRadius: 6,
        },
      ],
    }
  }, [data])

  const options = useMemo(
    () => ({
      responsive: true,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        title: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => formatDuration(ctx.raw),
          },
        },
      },
      scales: {
        x: {
          ticks: {
            callback: (v) => formatDuration(v),
          },
        },
      },
    }),
    []
  )

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
        <button onClick={load} disabled={loading}>{loading ? 'Loading…' : 'Refresh'}</button>
        <span style={{ opacity: 0.85 }}>
          API: <a href="/api/healthz" target="_blank" rel="noreferrer">/api/healthz</a>
        </span>
      </div>

      {error && <div className="err">Error: {error}</div>}

      <div style={{ minHeight: 260 }}>
        <Bar data={chart} options={options} />
      </div>

      <div style={{ opacity: 0.75, marginTop: 10, fontSize: 12 }}>
        {data?.items?.length ? (
          <span>
            Top zone: <b>{data.items[0].zoneName || data.items[0].zoneId}</b> ({formatDuration(data.items[0].totalSeconds)})
          </span>
        ) : (
          <span>No completed visits in the last 24h yet.</span>
        )}
      </div>
    </div>
  )
}
