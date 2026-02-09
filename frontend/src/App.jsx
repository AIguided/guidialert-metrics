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

  const [zones, setZones] = useState([])
  const [zonesError, setZonesError] = useState(null)
  const [zonesLoading, setZonesLoading] = useState(false)

  const [zoneForm, setZoneForm] = useState({ zoneId: '', zoneName: '', x: '', y: '', z: '' })

  const [anchors, setAnchors] = useState([])
  const [anchorsError, setAnchorsError] = useState(null)
  const [anchorsLoading, setAnchorsLoading] = useState(false)

  const [anchorForm, setAnchorForm] = useState({ anchorId: '', anchorName: '', x: '', y: '', z: '' })

  // Floorplan state
  const [floorplans, setFloorplans] = useState([])
  const [floorplansError, setFloorplansError] = useState(null)
  const [floorplansLoading, setFloorplansLoading] = useState(false)
  const [floorplanForm, setFloorplanForm] = useState({ floorId: '', floorName: '' })
  const [floorplanImage, setFloorplanImage] = useState(null)
  const [selectedFloorplan, setSelectedFloorplan] = useState(null)

  function startEditZone(z) {
    setZoneForm({
      zoneId: z.zoneId ?? '',
      zoneName: z.zoneName ?? '',
      x: z.x ?? '',
      y: z.y ?? '',
      z: z.z ?? '',
    })
  }

  function startEditAnchor(a) {
    setAnchorForm({
      anchorId: a.anchorId ?? '',
      anchorName: a.anchorName ?? '',
      x: a.x ?? '',
      y: a.y ?? '',
      z: a.z ?? '',
    })
  }

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

  async function loadZones() {
    setZonesLoading(true)
    setZonesError(null)
    try {
      const res = await fetch('/api/zones')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setZones(json.items || [])
    } catch (e) {
      setZonesError(String(e?.message ?? e))
    } finally {
      setZonesLoading(false)
    }
  }

  async function loadAnchors() {
    setAnchorsLoading(true)
    setAnchorsError(null)
    try {
      const res = await fetch('/api/anchors')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setAnchors(json.items || [])
    } catch (e) {
      setAnchorsError(String(e?.message ?? e))
    } finally {
      setAnchorsLoading(false)
    }
  }

  function parseNum(v) {
    if (v === '' || v == null) return null
    const n = Number(v)
    return Number.isFinite(n) ? n : null
  }

  async function submitZone(e) {
    e.preventDefault()
    setZonesError(null)
    try {
      const body = {
        zoneId: zoneForm.zoneId.trim(),
        zoneName: zoneForm.zoneName.trim(),
        x: parseNum(zoneForm.x),
        y: parseNum(zoneForm.y),
        z: parseNum(zoneForm.z),
      }
      if (!body.zoneId || !body.zoneName) throw new Error('zoneId and zoneName are required')

      const res = await fetch('/api/zones', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const t = await res.text()
        throw new Error(t || `HTTP ${res.status}`)
      }
      setZoneForm({ zoneId: '', zoneName: '', x: '', y: '', z: '' })
      await loadZones()
      await load()
    } catch (e2) {
      setZonesError(String(e2?.message ?? e2))
    }
  }

  async function submitAnchor(e) {
    e.preventDefault()
    setAnchorsError(null)
    try {
      const body = {
        anchorId: anchorForm.anchorId.trim(),
        anchorName: anchorForm.anchorName.trim(),
        x: parseNum(anchorForm.x),
        y: parseNum(anchorForm.y),
        z: parseNum(anchorForm.z),
      }
      if (!body.anchorId || !body.anchorName) throw new Error('anchorId and anchorName are required')
      if (body.x == null && body.y == null && body.z == null) throw new Error('at least one of x,y,z is required')

      const res = await fetch('/api/anchors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const t = await res.text()
        throw new Error(t || `HTTP ${res.status}`)
      }
      setAnchorForm({ anchorId: '', anchorName: '', x: '', y: '', z: '' })
      await loadAnchors()
    } catch (e2) {
      setAnchorsError(String(e2?.message ?? e2))
    }
  }

  // Floorplan functions
  async function loadFloorplans() {
    setFloorplansLoading(true)
    setFloorplansError(null)
    try {
      const res = await fetch('/api/floorplans')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setFloorplans(json.items || [])
    } catch (e) {
      setFloorplansError(String(e?.message ?? e))
    } finally {
      setFloorplansLoading(false)
    }
  }

  function startEditFloorplan(f) {
    setFloorplanForm({
      floorId: f.floorId ?? '',
      floorName: f.floorName ?? '',
    })
    setFloorplanImage(null)
  }

  async function submitFloorplan(e) {
    e.preventDefault()
    setFloorplansError(null)
    try {
      const floorId = floorplanForm.floorId.trim()
      const floorName = floorplanForm.floorName.trim()
      if (!floorId || !floorName) throw new Error('floorId and floorName are required')

      const formData = new FormData()
      formData.append('floorId', floorId)
      formData.append('floorName', floorName)
      if (floorplanImage) {
        formData.append('image', floorplanImage)
      }

      const res = await fetch('/api/floorplans', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const t = await res.text()
        throw new Error(t || `HTTP ${res.status}`)
      }
      setFloorplanForm({ floorId: '', floorName: '' })
      setFloorplanImage(null)
      await loadFloorplans()
    } catch (e2) {
      setFloorplansError(String(e2?.message ?? e2))
    }
  }

  async function deleteFloorplan(floorId) {
    if (!confirm(`Delete floorplan "${floorId}"?`)) return
    setFloorplansError(null)
    try {
      const res = await fetch(`/api/floorplans/${encodeURIComponent(floorId)}`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        const t = await res.text()
        throw new Error(t || `HTTP ${res.status}`)
      }
      if (selectedFloorplan?.floorId === floorId) {
        setSelectedFloorplan(null)
      }
      await loadFloorplans()
    } catch (e2) {
      setFloorplansError(String(e2?.message ?? e2))
    }
  }

  function viewFloorplanImage(f) {
    if (f.hasImage) {
      setSelectedFloorplan(f)
    }
  }

  useEffect(() => {
    load()
    loadZones()
    loadAnchors()
    loadFloorplans()
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

      <hr style={{ border: 'none', borderTop: '1px solid #223055', margin: '18px 0' }} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Zone Admin</div>
          <div style={{ fontSize: 12, opacity: 0.8 }}>Add/update zones and set x,y,z coordinates.</div>
        </div>
        <button onClick={loadZones} disabled={zonesLoading}>{zonesLoading ? 'Loading…' : 'Refresh zones'}</button>
      </div>

      {zonesError && <div className="err">Zones error: {zonesError}</div>}

      <form onSubmit={submitZone} style={{ display: 'flex', gap: 10, marginTop: 12, flexWrap: 'wrap' }}>
        <input
          placeholder="zoneId (e.g. zone-F)"
          value={zoneForm.zoneId}
          onChange={(e) => setZoneForm((s) => ({ ...s, zoneId: e.target.value }))}
        />
        <input
          placeholder="zoneName"
          value={zoneForm.zoneName}
          onChange={(e) => setZoneForm((s) => ({ ...s, zoneName: e.target.value }))}
          style={{ minWidth: 180 }}
        />
        <input placeholder="x" value={zoneForm.x} onChange={(e) => setZoneForm((s) => ({ ...s, x: e.target.value }))} />
        <input placeholder="y" value={zoneForm.y} onChange={(e) => setZoneForm((s) => ({ ...s, y: e.target.value }))} />
        <input placeholder="z" value={zoneForm.z} onChange={(e) => setZoneForm((s) => ({ ...s, z: e.target.value }))} />
        <button type="submit">Save zone</button>
        <button
          type="button"
          onClick={() => setZoneForm({ zoneId: '', zoneName: '', x: '', y: '', z: '' })}
          style={{ background: '#334155' }}
        >
          Clear
        </button>
      </form>

      <div style={{ marginTop: 12, overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ textAlign: 'left', opacity: 0.9 }}>
              <th style={{ padding: '8px 6px' }}>zoneId</th>
              <th style={{ padding: '8px 6px' }}>zoneName</th>
              <th style={{ padding: '8px 6px' }}>x</th>
              <th style={{ padding: '8px 6px' }}>y</th>
              <th style={{ padding: '8px 6px' }}>z</th>
              <th style={{ padding: '8px 6px' }}></th>
            </tr>
          </thead>
          <tbody>
            {(zones || []).map((z) => (
              <tr key={`${z.siteId}:${z.zoneId}`} style={{ borderTop: '1px solid #223055' }}>
                <td style={{ padding: '8px 6px', whiteSpace: 'nowrap' }}>{z.zoneId}</td>
                <td style={{ padding: '8px 6px' }}>{z.zoneName}</td>
                <td style={{ padding: '8px 6px' }}>{z.x ?? ''}</td>
                <td style={{ padding: '8px 6px' }}>{z.y ?? ''}</td>
                <td style={{ padding: '8px 6px' }}>{z.z ?? ''}</td>
                <td style={{ padding: '8px 6px' }}>
                  <button
                    type="button"
                    onClick={() => startEditZone(z)}
                    style={{ background: '#22c55e' }}
                  >
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <hr style={{ border: 'none', borderTop: '1px solid #223055', margin: '18px 0' }} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Anchor Admin</div>
          <div style={{ fontSize: 12, opacity: 0.8 }}>Add/update anchors and track position history.</div>
        </div>
        <button onClick={loadAnchors} disabled={anchorsLoading}>{anchorsLoading ? 'Loading…' : 'Refresh anchors'}</button>
      </div>

      {anchorsError && <div className="err">Anchors error: {anchorsError}</div>}

      <form onSubmit={submitAnchor} style={{ display: 'flex', gap: 10, marginTop: 12, flexWrap: 'wrap' }}>
        <input
          placeholder="anchorId (e.g. anchor-1)"
          value={anchorForm.anchorId}
          onChange={(e) => setAnchorForm((s) => ({ ...s, anchorId: e.target.value }))}
        />
        <input
          placeholder="anchorName"
          value={anchorForm.anchorName}
          onChange={(e) => setAnchorForm((s) => ({ ...s, anchorName: e.target.value }))}
          style={{ minWidth: 180 }}
        />
        <input placeholder="x" value={anchorForm.x} onChange={(e) => setAnchorForm((s) => ({ ...s, x: e.target.value }))} />
        <input placeholder="y" value={anchorForm.y} onChange={(e) => setAnchorForm((s) => ({ ...s, y: e.target.value }))} />
        <input placeholder="z" value={anchorForm.z} onChange={(e) => setAnchorForm((s) => ({ ...s, z: e.target.value }))} />
        <button type="submit">Save anchor</button>
        <button
          type="button"
          onClick={() => setAnchorForm({ anchorId: '', anchorName: '', x: '', y: '', z: '' })}
          style={{ background: '#334155' }}
        >
          Clear
        </button>
      </form>

      <div style={{ marginTop: 12, overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ textAlign: 'left', opacity: 0.9 }}>
              <th style={{ padding: '8px 6px' }}>anchorId</th>
              <th style={{ padding: '8px 6px' }}>anchorName</th>
              <th style={{ padding: '8px 6px' }}>x</th>
              <th style={{ padding: '8px 6px' }}>y</th>
              <th style={{ padding: '8px 6px' }}>z</th>
              <th style={{ padding: '8px 6px' }}>updated</th>
              <th style={{ padding: '8px 6px' }}></th>
            </tr>
          </thead>
          <tbody>
            {(anchors || []).map((a) => (
              <tr key={`${a.siteId}:${a.anchorId}`} style={{ borderTop: '1px solid #223055' }}>
                <td style={{ padding: '8px 6px', whiteSpace: 'nowrap' }}>{a.anchorId}</td>
                <td style={{ padding: '8px 6px' }}>{a.anchorName}</td>
                <td style={{ padding: '8px 6px' }}>{a.x ?? ''}</td>
                <td style={{ padding: '8px 6px' }}>{a.y ?? ''}</td>
                <td style={{ padding: '8px 6px' }}>{a.z ?? ''}</td>
                <td style={{ padding: '8px 6px' }}>{a.updatedAt ? new Date(a.updatedAt).toLocaleString() : ''}</td>
                <td style={{ padding: '8px 6px' }}>
                  <button
                    type="button"
                    onClick={() => startEditAnchor(a)}
                    style={{ background: '#22c55e' }}
                  >
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <hr style={{ border: 'none', borderTop: '1px solid #223055', margin: '18px 0' }} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Floorplan Admin</div>
          <div style={{ fontSize: 12, opacity: 0.8 }}>Upload floorplan images. Click a row to view the image.</div>
        </div>
        <button onClick={loadFloorplans} disabled={floorplansLoading}>{floorplansLoading ? 'Loading…' : 'Refresh floorplans'}</button>
      </div>

      {floorplansError && <div className="err">Floorplans error: {floorplansError}</div>}

      <form onSubmit={submitFloorplan} style={{ display: 'flex', gap: 10, marginTop: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          placeholder="floorId (e.g. floor-1)"
          value={floorplanForm.floorId}
          onChange={(e) => setFloorplanForm((s) => ({ ...s, floorId: e.target.value }))}
        />
        <input
          placeholder="floorName"
          value={floorplanForm.floorName}
          onChange={(e) => setFloorplanForm((s) => ({ ...s, floorName: e.target.value }))}
          style={{ minWidth: 180 }}
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', background: '#334155', padding: '6px 12px', borderRadius: 6 }}>
          <span>{floorplanImage ? floorplanImage.name : 'Choose image...'}</span>
          <input
            type="file"
            accept="image/png,image/jpeg,image/gif,image/webp"
            onChange={(e) => setFloorplanImage(e.target.files?.[0] || null)}
            style={{ display: 'none' }}
          />
        </label>
        <button type="submit">Save floorplan</button>
        <button
          type="button"
          onClick={() => { setFloorplanForm({ floorId: '', floorName: '' }); setFloorplanImage(null) }}
          style={{ background: '#334155' }}
        >
          Clear
        </button>
      </form>

      <div style={{ marginTop: 12, overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ textAlign: 'left', opacity: 0.9 }}>
              <th style={{ padding: '8px 6px' }}>floorId</th>
              <th style={{ padding: '8px 6px' }}>floorName</th>
              <th style={{ padding: '8px 6px' }}>hasImage</th>
              <th style={{ padding: '8px 6px' }}>updated</th>
              <th style={{ padding: '8px 6px' }}></th>
            </tr>
          </thead>
          <tbody>
            {(floorplans || []).map((f) => (
              <tr
                key={`${f.siteId}:${f.floorId}`}
                style={{
                  borderTop: '1px solid #223055',
                  cursor: f.hasImage ? 'pointer' : 'default',
                  background: selectedFloorplan?.floorId === f.floorId ? '#1e3a5f' : 'transparent',
                }}
                onClick={() => viewFloorplanImage(f)}
              >
                <td style={{ padding: '8px 6px', whiteSpace: 'nowrap' }}>{f.floorId}</td>
                <td style={{ padding: '8px 6px' }}>{f.floorName}</td>
                <td style={{ padding: '8px 6px' }}>{f.hasImage ? 'Yes' : 'No'}</td>
                <td style={{ padding: '8px 6px' }}>{f.updatedAt ? new Date(f.updatedAt).toLocaleString() : ''}</td>
                <td style={{ padding: '8px 6px', display: 'flex', gap: 6 }}>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); startEditFloorplan(f) }}
                    style={{ background: '#22c55e' }}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); deleteFloorplan(f.floorId) }}
                    style={{ background: '#ef4444' }}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedFloorplan && (
        <div style={{ marginTop: 16, padding: 12, background: '#1e293b', borderRadius: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>
              {selectedFloorplan.floorName} ({selectedFloorplan.floorId})
            </div>
            <button
              type="button"
              onClick={() => setSelectedFloorplan(null)}
              style={{ background: '#64748b', padding: '4px 10px', fontSize: 12 }}
            >
              Close
            </button>
          </div>
          <img
            src={`/api/floorplans/${encodeURIComponent(selectedFloorplan.floorId)}/image`}
            alt={selectedFloorplan.floorName}
            style={{ maxWidth: '100%', maxHeight: 500, borderRadius: 6, display: 'block' }}
          />
        </div>
      )}
    </div>
  )
}
