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

  const [zoneForm, setZoneForm] = useState({ zoneId: '', zoneName: '', x: '', y: '', z: '', audioId: '' })

  const [anchors, setAnchors] = useState([])
  const [anchorsError, setAnchorsError] = useState(null)
  const [anchorsLoading, setAnchorsLoading] = useState(false)

  const [anchorForm, setAnchorForm] = useState({ anchorId: '', anchorName: '', x: '', y: '', z: '' })

  const [queryInput, setQueryInput] = useState('')
  const [queryResult, setQueryResult] = useState(null)
  const [queryError, setQueryError] = useState(null)
  const [queryLoading, setQueryLoading] = useState(false)

  const [audioFiles, setAudioFiles] = useState([])
  const [audioError, setAudioError] = useState(null)
  const [audioLoading, setAudioLoading] = useState(false)
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadDescription, setUploadDescription] = useState('')
  const [uploading, setUploading] = useState(false)

  function startEditZone(z) {
    setZoneForm({
      zoneId: z.zoneId ?? '',
      zoneName: z.zoneName ?? '',
      x: z.x ?? '',
      y: z.y ?? '',
      z: z.z ?? '',
      audioId: z.audioId ?? '',
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
        audioId: parseNum(zoneForm.audioId),
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
      setZoneForm({ zoneId: '', zoneName: '', x: '', y: '', z: '', audioId: '' })
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

  async function executeQuery() {
    if (!queryInput.trim()) {
      setQueryError('Please enter a SQL query')
      return
    }

    setQueryLoading(true)
    setQueryError(null)
    setQueryResult(null)
    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: queryInput }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }
      const json = await res.json()
      setQueryResult(json)
    } catch (e) {
      setQueryError(String(e?.message ?? e))
    } finally {
      setQueryLoading(false)
    }
  }

  async function loadAudioFiles() {
    setAudioLoading(true)
    setAudioError(null)
    try {
      const res = await fetch('/api/audio/list')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setAudioFiles(json.items || [])
    } catch (e) {
      setAudioError(String(e?.message ?? e))
    } finally {
      setAudioLoading(false)
    }
  }

  async function uploadAudio(e) {
    e.preventDefault()
    if (!uploadFile) {
      setAudioError('Please select a file')
      return
    }

    setUploading(true)
    setAudioError(null)
    try {
      const formData = new FormData()
      formData.append('file', uploadFile)
      formData.append('description', uploadDescription)

      const res = await fetch('/api/audio/upload', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }
      setUploadFile(null)
      setUploadDescription('')
      await loadAudioFiles()
    } catch (e) {
      setAudioError(String(e?.message ?? e))
    } finally {
      setUploading(false)
    }
  }

  async function deleteAudio(id) {
    if (!confirm('Are you sure you want to delete this audio file?')) return

    setAudioError(null)
    try {
      const res = await fetch(`/api/audio/${id}`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }
      await loadAudioFiles()
      await loadZones() // Reload zones in case audio_id was cleared
    } catch (e) {
      setAudioError(String(e?.message ?? e))
    }
  }

  async function cleanupOrphanedAudio() {
    setAudioError(null)
    try {
      const res = await fetch('/api/audio/cleanup-orphaned', {
        method: 'POST',
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }
      const json = await res.json()
      alert(`Cleaned ${json.cleanedCount} orphaned audio reference(s)${json.cleanedZones.length > 0 ? `: ${json.cleanedZones.join(', ')}` : ''}`)
      await loadZones()
    } catch (e) {
      setAudioError(String(e?.message ?? e))
    }
  }

  function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  useEffect(() => {
    load()
    loadZones()
    loadAnchors()
    loadAudioFiles()
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
        <input placeholder="audioId" value={zoneForm.audioId} onChange={(e) => setZoneForm((s) => ({ ...s, audioId: e.target.value }))} />
        <button type="submit">Save zone</button>
        <button
          type="button"
          onClick={() => setZoneForm({ zoneId: '', zoneName: '', x: '', y: '', z: '', audioId: '' })}
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
              <th style={{ padding: '8px 6px' }}>audioId</th>
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
                  {z.audioId ? (
                    <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                      <span>{z.audioId}</span>
                      <button
                        type="button"
                        onClick={() => {
                          // Play audio in a new Audio context to avoid browser restrictions on autoplay in certain cases
                          const audio = new Audio(`/api/audio/${z.audioId}`)
                          audio.play()
                        }}
                        style={{ background: '#10b981', padding: '2px 6px', fontSize: 10 }}
                      >
                        ▶
                      </button>
                    </div>
                  ) : (
                    '-'
                  )}
                </td>
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

      <div>
        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Query Test</div>
        <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 12 }}>
          Execute SQL queries to test the database. Only SELECT queries are allowed.
        </div>

        <div style={{ display: 'flex', gap: 10, marginBottom: 12, flexDirection: 'column' }}>
          <textarea
            placeholder="Enter SQL query (e.g., SELECT * FROM zones LIMIT 10)"
            value={queryInput}
            onChange={(e) => setQueryInput(e.target.value)}
            style={{
              width: '100%',
              minHeight: 100,
              padding: 8,
              fontFamily: 'monospace',
              fontSize: 13,
              background: '#0f172a',
              border: '1px solid #334155',
              borderRadius: 4,
              color: '#e2e8f0',
              resize: 'vertical',
            }}
          />
          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={executeQuery} disabled={queryLoading}>
              {queryLoading ? 'Executing...' : 'Execute Query'}
            </button>
            <button
              type="button"
              onClick={() => {
                setQueryInput('')
                setQueryResult(null)
                setQueryError(null)
              }}
              style={{ background: '#334155' }}
            >
              Clear
            </button>
          </div>
        </div>

        {queryError && <div className="err">Query error: {queryError}</div>}

        {queryResult && (
          <div>
            <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 8 }}>
              {queryResult.rowCount} row{queryResult.rowCount !== 1 ? 's' : ''} returned
            </div>
            <div style={{ overflowX: 'auto', maxHeight: 400, overflow: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead style={{ position: 'sticky', top: 0, background: '#0f172a' }}>
                  <tr style={{ textAlign: 'left', opacity: 0.9 }}>
                    {queryResult.columns.map((col) => (
                      <th key={col} style={{ padding: '8px 6px', borderBottom: '2px solid #223055' }}>
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {queryResult.rows.map((row, idx) => (
                    <tr key={idx} style={{ borderTop: '1px solid #223055' }}>
                      {queryResult.columns.map((col) => (
                        <td key={col} style={{ padding: '8px 6px', whiteSpace: 'nowrap' }}>
                          {row[col] == null ? (
                            <span style={{ opacity: 0.5 }}>null</span>
                          ) : (
                            String(row[col])
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <hr style={{ border: 'none', borderTop: '1px solid #223055', margin: '18px 0' }} />

      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Audio Files</div>
            <div style={{ fontSize: 12, opacity: 0.8 }}>Upload and manage audio files (.mp3, .wav)</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={cleanupOrphanedAudio} style={{ background: '#f59e0b' }}>
              Clean Orphaned
            </button>
            <button onClick={loadAudioFiles} disabled={audioLoading}>
              {audioLoading ? 'Loading...' : 'Refresh'}
            </button>
          </div>
        </div>

        {audioError && <div className="err">Audio error: {audioError}</div>}

        <form onSubmit={uploadAudio} style={{ marginTop: 12, display: 'flex', gap: 10, flexDirection: 'column' }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              type="file"
              accept=".mp3,.wav,audio/mpeg,audio/wav"
              onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
              style={{ flex: 1, minWidth: 200 }}
            />
            <input
              placeholder="Description (optional)"
              value={uploadDescription}
              onChange={(e) => setUploadDescription(e.target.value)}
              style={{ minWidth: 200 }}
            />
            <button type="submit" disabled={uploading || !uploadFile}>
              {uploading ? 'Uploading...' : 'Upload'}
            </button>
          </div>
          {uploadFile && (
            <div style={{ fontSize: 12, opacity: 0.8 }}>
              Selected: {uploadFile.name} ({formatFileSize(uploadFile.size)})
            </div>
          )}
        </form>

        <div style={{ marginTop: 12, overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ textAlign: 'left', opacity: 0.9 }}>
                <th style={{ padding: '8px 6px' }}>ID</th>
                <th style={{ padding: '8px 6px' }}>Filename</th>
                <th style={{ padding: '8px 6px' }}>Size</th>
                <th style={{ padding: '8px 6px' }}>Description</th>
                <th style={{ padding: '8px 6px' }}>Uploaded</th>
                <th style={{ padding: '8px 6px' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {(audioFiles || []).map((audioFile) => (
                <tr key={audioFile.id} style={{ borderTop: '1px solid #223055' }}>
                  <td style={{ padding: '8px 6px' }}>{audioFile.id}</td>
                  <td style={{ padding: '8px 6px', whiteSpace: 'nowrap' }}>{audioFile.filename}</td>
                  <td style={{ padding: '8px 6px' }}>{formatFileSize(audioFile.fileSize)}</td>
                  <td style={{ padding: '8px 6px' }}>{audioFile.description || '-'}</td>
                  <td style={{ padding: '8px 6px', whiteSpace: 'nowrap' }}>
                    {audioFile.uploadedAt ? new Date(audioFile.uploadedAt).toLocaleString() : '-'}
                  </td>
                  <td style={{ padding: '8px 6px', display: 'flex', gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => {
                        const audio = new Audio(`/api/audio/${audioFile.id}`)
                        audio.play()
                      }}
                      style={{ background: '#10b981', padding: '4px 8px', fontSize: 11 }}
                    >
                      ▶ Play
                    </button>
                    <a
                      href={`/api/audio/${audioFile.id}`}
                      download
                      style={{
                        padding: '4px 8px',
                        background: '#3b82f6',
                        color: 'white',
                        textDecoration: 'none',
                        borderRadius: 4,
                        fontSize: 11,
                      }}
                    >
                      Download
                    </a>
                    <button
                      type="button"
                      onClick={() => deleteAudio(audioFile.id)}
                      style={{ background: '#ef4444', padding: '4px 8px', fontSize: 11 }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {audioFiles && audioFiles.length === 0 && (
            <div style={{ padding: '20px', textAlign: 'center', opacity: 0.6, fontSize: 12 }}>
              No audio files uploaded yet
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
