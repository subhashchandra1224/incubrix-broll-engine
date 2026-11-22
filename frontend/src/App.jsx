import { useState, useEffect, useRef } from 'react'
import { createJob, getJobStatus, fileDownloadUrl, newIdempotencyKey } from './api'

const RATIOS = ['16:9', '9:16', '1:1']

export default function App() {
  // --- form state ---
  const [mode, setMode] = useState('script')
  const [script, setScript] = useState(
    'Saving money starts with small decisions. Track your monthly expenses carefully. A clear budget builds long term security.'
  )
  const [audioUrl, setAudioUrl] = useState('')
  const [scenes, setScenes] = useState([{ text: '', visual_hint: '' }])
  const [ratios, setRatios] = useState(['16:9'])
  const [srt, setSrt] = useState(true)
  const [burnIn, setBurnIn] = useState(false)
  const [style, setStyle] = useState('')
  const [avoidText, setAvoidText] = useState('')
  const [voice, setVoice] = useState('')

  // --- job state ---
  const [idemKey, setIdemKey] = useState(() => newIdempotencyKey())
  const [job, setJob] = useState(null)
  const [submitErr, setSubmitErr] = useState(null)
  const [polling, setPolling] = useState(false)
  const timer = useRef(null)

  // --- build request payload ---
  function buildPayload() {
    const p = {
      aspect_ratios: ratios,
      captions: { srt, burn_in: burnIn },
    }
    if (style.trim()) p.style = style.trim()
    if (avoidText.trim())
      p.avoid = avoidText.split(',').map((s) => s.trim()).filter(Boolean)
    if (voice.trim()) p.voice = voice.trim()

    if (mode === 'script') p.script = script
    else if (mode === 'audio_url') p.audio_url = audioUrl
    else if (mode === 'scenes') p.scenes = scenes.filter((s) => s.text.trim())
    return p
  }

  // --- submit ---
  async function handleSubmit() {
    setSubmitErr(null)
    setJob(null)
    setPolling(false)
    try {
      const result = await createJob(buildPayload(), idemKey)
      if (result.error) {
        setSubmitErr(result.error)
        return
      }
      setJob({ job_id: result.job_id, status: 'queued', progress: 0 })
      setPolling(true)
    } catch (e) {
      setSubmitErr({ code: 'NETWORK_ERROR', message: String(e) })
    }
  }

  // --- poll ---
  useEffect(() => {
    if (!polling || !job?.job_id) return
    let active = true
    const poll = async () => {
      try {
        const st = await getJobStatus(job.job_id)
        if (!active) return
        setJob(st)
        if (st.status === 'succeeded' || st.status === 'failed') {
          setPolling(false)
        }
      } catch (e) {
        console.error('poll error', e)
      }
    }
    poll()
    timer.current = setInterval(poll, 2000)
    return () => {
      active = false
      clearInterval(timer.current)
    }
  }, [polling, job?.job_id])

  // --- retry (same key) ---
  function handleRetry() {
    setJob(null)
    setPolling(false)
    handleSubmit()
  }

  // --- new job (new key) ---
  function handleNew() {
    setIdemKey(newIdempotencyKey())
    setJob(null)
    setPolling(false)
    setSubmitErr(null)
  }

  // --- helpers ---
  function toggleRatio(r) {
    setRatios((prev) =>
      prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r]
    )
  }

  function updateScene(i, field, val) {
    setScenes((prev) =>
      prev.map((s, idx) => (idx === i ? { ...s, [field]: val } : s))
    )
  }

  function addScene() {
    setScenes((prev) => [...prev, { text: '', visual_hint: '' }])
  }

  function removeScene(i) {
    setScenes((prev) => prev.filter((_, idx) => idx !== i))
  }

  // --- derived ---
  const isTerminal = job && (job.status === 'succeeded' || job.status === 'failed')
  const result = job?.result
  const outputs = result?.outputs || []
  const links = job?.links || {}

  return (
    <div className="app">
      <header>
        <h1>B-roll Engine</h1>
        <div className="banner">
          All providers are <strong>mock</strong> — outputs are test data
          (sine-tone audio + colour-bar video). No real narration or footage is
          generated. Audio upload is not yet supported by the backend; use an
          audio URL instead.
        </div>
      </header>

      <main>
        {/* ============================ FORM ============================ */}
        <section className="form-section">
          <h2>Create a job</h2>

          {/* input mode */}
          <div className="mode-tabs">
            {['script', 'audio_url', 'scenes'].map((m) => (
              <button
                key={m}
                className={'mode-tab' + (mode === m ? ' active' : '')}
                onClick={() => setMode(m)}
              >
                {m === 'audio_url' ? 'Audio URL' : m.charAt(0).toUpperCase() + m.slice(1)}
              </button>
            ))}
          </div>

          {/* mode-specific fields */}
          {mode === 'script' && (
            <div className="field">
              <label>
                Script text{' '}
                <span className="test-badge">TEST DATA: mock TTS</span>
              </label>
              <textarea value={script} onChange={(e) => setScript(e.target.value)} />
            </div>
          )}

          {mode === 'audio_url' && (
            <div className="field">
              <label>
                Audio URL (mp3, wav, m4a){' '}
                <span className="test-badge">TEST DATA: mock STT</span>
              </label>
              <input
                type="url"
                placeholder="https://example.com/voiceover.mp3"
                value={audioUrl}
                onChange={(e) => setAudioUrl(e.target.value)}
              />
            </div>
          )}

          {mode === 'scenes' && (
            <div className="field">
              <label>
                Scene list (text + visual hint){' '}
                <span className="test-badge">TEST DATA: mock TTS</span>
              </label>
              {scenes.map((s, i) => (
                <div key={i} className="scene-row">
                  <input
                    type="text"
                    placeholder="Narration text"
                    value={s.text}
                    onChange={(e) => updateScene(i, 'text', e.target.value)}
                  />
                  <input
                    className="scene-hint"
                    type="text"
                    placeholder="Visual hint (optional)"
                    value={s.visual_hint || ''}
                    onChange={(e) => updateScene(i, 'visual_hint', e.target.value)}
                  />
                  {scenes.length > 1 && (
                    <button className="secondary" onClick={() => removeScene(i)}>
                      ✕
                    </button>
                  )}
                </div>
              ))}
              <button className="add-scene-btn" onClick={addScene}>
                + Add scene
              </button>
            </div>
          )}

          {/* aspect ratios */}
          <div className="field">
            <label>Aspect ratios</label>
            <div className="checkboxes">
              {RATIOS.map((r) => (
                <div key={r} className="checkbox">
                  <input
                    type="checkbox"
                    checked={ratios.includes(r)}
                    onChange={() => toggleRatio(r)}
                  />
                  <label>{r}</label>
                </div>
              ))}
            </div>
          </div>

          {/* captions */}
          <div className="field">
            <label>Captions</label>
            <div className="checkboxes">
              <div className="checkbox">
                <input type="checkbox" checked={srt} onChange={(e) => setSrt(e.target.checked)} />
                <label>Generate SRT</label>
              </div>
              <div className="checkbox">
                <input
                  type="checkbox"
                  checked={burnIn}
                  onChange={(e) => setBurnIn(e.target.checked)}
                />
                <label>Burn in captions</label>
              </div>
            </div>
          </div>

          {/* optional fields */}
          <div className="field">
            <label>Style (optional)</label>
            <input
              type="text"
              placeholder="bright, modern, real-world footage"
              value={style}
              onChange={(e) => setStyle(e.target.value)}
            />
          </div>

          <div className="field">
            <label>Avoid terms (comma-separated, optional)</label>
            <input
              type="text"
              placeholder="people's faces, alcohol"
              value={avoidText}
              onChange={(e) => setAvoidText(e.target.value)}
            />
          </div>

          <div className="field">
            <label>Voice (optional, text input only)</label>
            <input
              type="text"
              placeholder="en-IN-female"
              value={voice}
              onChange={(e) => setVoice(e.target.value)}
            />
          </div>

          {/* idempotency key */}
          <div className="field">
            <label>Idempotency-Key (reused on retry)</label>
            <input type="text" value={idemKey} readOnly />
          </div>

          {/* buttons */}
          <div className="btn-row">
            <button
              className="primary"
              onClick={handleSubmit}
              disabled={polling || (job && !isTerminal)}
            >
              {polling ? 'Processing…' : 'Submit job'}
            </button>
            {isTerminal && (
              <button className="secondary" onClick={handleRetry}>
                Retry (same key)
              </button>
            )}
            {isTerminal && (
              <button className="secondary" onClick={handleNew}>
                New job
              </button>
            )}
          </div>

          {/* submit error */}
          {submitErr && (
            <div className="error-box">
              <span className="code">{submitErr.code}</span>
              <p>{submitErr.message}</p>
              {submitErr.retryable && (
                <span className="retryable">Retryable: yes</span>
              )}
            </div>
          )}
        </section>

        {/* ============================ STATUS ============================ */}
        {job && (
          <section className="status-section">
            <h2>Job status</h2>
            <p>
              <strong>Job ID:</strong> {job.job_id}
            </p>
            <p>
              <span className={'status-badge status-' + job.status}>
                {job.status}
              </span>{' '}
              <span style={{ color: 'var(--text-dim)' }}>{job.progress}%</span>
            </p>
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: job.progress + '%' }}
              />
            </div>

            {/* job error */}
            {job.error && (
              <div className="error-box" style={{ marginTop: '0.7rem' }}>
                <span className="code">{job.error.code}</span>
                <p>{job.error.message}</p>
                <span className="retryable">
                  Retryable: {String(job.error.retryable)}
                </span>
              </div>
            )}
          </section>
        )}

        {/* ============================ RESULTS ============================ */}
        {job?.status === 'succeeded' && result && (
          <section className="results-section">
            <h2>
              Results{' '}
              {result.test_data && (
                <span className="test-badge">TEST DATA</span>
              )}
            </h2>

            {/* warnings */}
            {result.warnings && result.warnings.length > 0 && (
              <div className="warnings">
                <strong>Warnings:</strong>
                <ul className="warnings">
                  {result.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* video previews */}
            <div className="video-grid">
              {outputs.map((o, i) => {
                const fname = o.path?.split(/[\\/]/).pop() || ''
                const url = links[fname] || fileDownloadUrl(job.job_id, fname)
                return (
                  <div key={i} className="video-card">
                    <video src={url} controls preload="metadata" />
                    <div className="info">
                      <strong>{o.ratio}</strong>
                      {o.burned_in && (
                        <span className="test-badge" style={{ background: 'var(--ok)', color: '#1a1d28' }}>
                          Burned in
                        </span>
                      )}
                      {o.test_data && <span className="test-badge">TEST DATA</span>}
                      <br />
                      <a href={url} download={fname}>
                        Download {fname}
                      </a>
                      {o.validation_errors && o.validation_errors.length > 0 && (
                        <div style={{ color: 'var(--err)', fontSize: '0.75rem', marginTop: '0.3rem' }}>
                          Validation: {o.validation_errors.join(', ')}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* download links for SRT, timeline, manifest */}
            <div className="download-links">
              {result.srt_path && (
                <a
                  href={fileDownloadUrl(job.job_id, 'captions.srt')}
                  download
                >
                  captions.srt
                </a>
              )}
              <a href={fileDownloadUrl(job.job_id, 'timeline.json')} download>
                timeline.json
              </a>
              <a href={fileDownloadUrl(job.job_id, 'manifest.json')} download>
                manifest.json
              </a>
            </div>

            {/* scene details */}
            {result.scenes && result.scenes.length > 0 && (
              <div className="scenes-list">
                <h3 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>
                  Scene plan ({result.scenes.length} scenes)
                </h3>
                {result.scenes.map((sc, i) => (
                  <div key={i} className="scene-item">
                    <div className="narration">
                      <strong>{sc.scene_id}</strong>: {sc.text}
                    </div>
                    <div className="meta">
                      {sc.start_time}s – {sc.end_time}s ({sc.duration}s) |{' '}
                      query: {sc.search_query}
                      {sc.clip && (
                        <>
                          {' '}| clip: {sc.clip.provider}:{sc.clip.asset_id}{' '}
                          | licence: {sc.clip.license_name}
                          {sc.clip.test_data && ' (test data)'}{' '}
                          | relevance:{' '}
                          <span className="relevance">
                            {sc.relevance_score?.toFixed(4)}
                          </span>
                        </>
                      )}
                      {!sc.clip && ' | no clip (unavailable)'}
                    </div>
                    {sc.warnings && sc.warnings.length > 0 && (
                      <div className="meta" style={{ color: 'var(--warn)' }}>
                        ⚠ {sc.warnings.join('; ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* providers */}
            {result.providers && (
              <div style={{ marginTop: '1rem', fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                <strong>Providers:</strong>{' '}
                {Object.entries(result.providers).map(([k, v]) =>
                  `${k}=${Array.isArray(v) ? v.join('+') : v}`
                ).join(', ')}
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  )
}
