// ───────── PAGE 3 — /judgment ─────────────────────────────────────────────────
function Judgment() {
  const [phase, setPhase]   = React.useState('input');
  const [rules, setRules]   = React.useState('');
  const [mode, setMode]     = React.useState('scrape');
  const [url, setUrl]       = React.useState('');
  const [file, setFile]     = React.useState(null);
  const [fileId, setFileId] = React.useState(null);
  const [manual, setManual] = React.useState('');
  const [traces, setTraces] = React.useState([]);
  const [flash, setFlash]   = React.useState(0);
  const [report, setReport] = React.useState(null);
  const [verdictId, setVerdictId] = React.useState(null);
  const [inputError, setInputError] = React.useState(null);
  const [sseEnabled, setSseEnabled] = React.useState(false);
  const [sseBody, setSseBody] = React.useState(null);
  const [uploading, setUploading] = React.useState(false);

  const { models, defaultReasoning, defaultFast } = useModels();
  const [modelReasoning, setModelReasoning] = React.useState('');
  const [modelFast, setModelFast]           = React.useState('');
  const [limit, setLimit]                   = React.useState(null);
  React.useEffect(() => { if (!modelReasoning) setModelReasoning(defaultReasoning); }, [defaultReasoning]);
  React.useEffect(() => { if (!modelFast)      setModelFast(defaultFast);           }, [defaultFast]);

  // Pulse sigil on new traces
  React.useEffect(() => { if (phase === 'deliberating') setFlash((f) => f + 1); }, [traces.length]);

  // Real SSE
  useSSEFetch({
    endpoint: '/api/judgment',
    body: sseBody,
    enabled: sseEnabled && phase === 'deliberating' && sseBody !== null,
    onTrace: (text) => setTraces((t) => [...t, text]),
    onFinal: (ev) => {
      setVerdictId(ev.verdict_id);
      setReport(ev.report);
      setPhase('ruling');
    },
    onError: (msg) => {
      setSseEnabled(false);
      setPhase('input');
      setInputError(msg);
    },
  });

  const submit = async (e) => {
    e && e.preventDefault();
    setInputError(null);

    // Scrape mode requires a hackathon URL with submissions
    if (mode === 'scrape') {
      const trimmed = url.trim();
      if (!trimmed) {
        setInputError('Please provide a hackathon link to proceed.');
        return;
      }
      setPhase('deliberating');
      setTraces(['Checking hackathon URL…']);

      try {
        const resp = await fetch('/api/validate_hackathon', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: trimmed }),
        });
        const result = await resp.json();
        if (!result.valid) {
          setPhase('input');
          setInputError(result.error || 'This does not appear to be a hackathon page with submissions.');
          return;
        }
        setTraces((t) => [...t, `Found ${result.submission_count} submission(s) — starting judgment…`]);
        const body = { rules, source_type: 'hackathon_url', hackathon_url: trimmed, model_reasoning: modelReasoning, model_fast: modelFast, limit };
        setSseBody(body);
        setSseEnabled(true);
      } catch {
        // Validation endpoint unreachable — proceed anyway; SSE will surface any real errors.
        setTraces((t) => [...t, 'Proceeding to judgment…']);
        const body = { rules, source_type: 'hackathon_url', hackathon_url: trimmed, model_reasoning: modelReasoning, model_fast: modelFast, limit };
        setSseBody(body);
        setSseEnabled(true);
      }
      return;
    }

    setPhase('deliberating');
    setTraces([]);

    // Upload mode: upload file first, then stream
    if (mode === 'upload' && file) {
      setUploading(true);
      try {
        const fd = new FormData();
        fd.append('file', file);
        const resp = await fetch('/api/upload', { method: 'POST', body: fd });
        const data = await resp.json();
        if (data.file_id) {
          const body = { rules, source_type: 'uploaded_file', uploaded_file_id: data.file_id, model_reasoning: modelReasoning, model_fast: modelFast, limit };
          setSseBody(body);
          setSseEnabled(true);
        } else {
          throw new Error(data.error || 'upload failed');
        }
      } catch (err) {
        setPhase('input');
        setInputError(err.message);
      } finally {
        setUploading(false);
      }
    } else if (mode === 'manual' && manual.trim()) {
      const body = { rules, source_type: 'manual_text', manual_text: manual.trim(), model_reasoning: modelReasoning, model_fast: modelFast, limit };
      setSseBody(body);
      setSseEnabled(true);
    } else {
      setPhase('input');
      setInputError('Please provide submissions to judge.');
    }
  };

  const visibleTraces = traces;

  return (
    <div className="route" data-screen-label={`03 Judgment — ${phase}`}>
      <div className="topbar-bg" />
      <TopBar meta={phase === 'input' ? 'awaiting the bench' : phase === 'deliberating' ? 'deliberating' : 'ruling rendered'} />

      {phase === 'input' && (
        <JudgmentInput
          rules={rules} setRules={setRules}
          mode={mode} setMode={setMode}
          url={url} setUrl={setUrl}
          file={file} setFile={setFile}
          manual={manual} setManual={setManual}
          submit={submit} uploading={uploading}
          models={models}
          modelReasoning={modelReasoning} setModelReasoning={setModelReasoning}
          modelFast={modelFast} setModelFast={setModelFast}
          limit={limit} setLimit={setLimit}
          inputError={inputError}
        />
      )}
      {phase === 'deliberating' && <JudgmentDeliberating traces={visibleTraces} flash={flash} />}
      {phase === 'ruling' && <JudgmentRuling report={report} verdictId={verdictId} />}
    </div>
  );
}

// ─── Input ───────────────────────────────────────────────────────────────────

function JudgmentInput({ rules, setRules, mode, setMode, url, setUrl, file, setFile, manual, setManual, submit, uploading, models, modelReasoning, setModelReasoning, modelFast, setModelFast, limit, setLimit, inputError }) {
  return (
    <div className="wrap fade-in" style={{ paddingTop: 180, paddingBottom: 120 }}>
      <div className="section-label fade-in fade-in-delay-1" style={{ marginBottom: 28 }}>II. PASS JUDGMENT</div>
      <h1 className="h-display fade-in fade-in-delay-1" style={{ marginBottom: 64, maxWidth: 1000 }}>
        Call the <em>bench.</em>
      </h1>

      <form onSubmit={submit} className="fade-in fade-in-delay-2" style={{ maxWidth: 1000 }}>

        {/* RULES OF THE COURT */}
        <section style={{ marginBottom: 72 }}>
          <div className="rules-field-label">— THE RULES OF THE COURT —</div>
          <textarea
            className="field-area rules-field"
            placeholder="Paste the judging rubric, or leave blank for the default."
            value={rules}
            onChange={(e) => setRules(e.target.value)}
          />
          <div className="rules-field-hint">
            Optional. By default the court rules on novelty (30%), technical depth (30%), real-world impact (25%), and presentation (15%).
          </div>
        </section>

        {/* THE SUBMISSIONS */}
        <section style={{ marginBottom: 56 }}>
          <div className="rules-field-label" style={{ marginBottom: 16 }}>— THE SUBMISSIONS —</div>

          <div className="tab-rail" role="tablist">
            {[['scrape', 'SCRAPE A HACKATHON'], ['upload', 'UPLOAD A FILE'], ['manual', 'ENTER MANUALLY']].map(([key, label]) => (
              <button
                key={key}
                type="button"
                role="tab"
                className={`tab ${mode === key ? 'active' : ''}`}
                onClick={() => setMode(key)}
              >
                {label}
              </button>
            ))}
          </div>

          {mode === 'scrape' && (
            <div className="tab-panel" key="scrape">
              <input
                className={`field-line${inputError && mode === 'scrape' ? ' field-error' : ''}`}
                type="text"
                placeholder="https://lablab.ai/event/…"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                autoFocus
              />
              {inputError && mode === 'scrape' && (
                <div className="field-error-msg">{inputError}</div>
              )}
              <div className="scrape-hint">the court will summon every submission from this page</div>
            </div>
          )}

          {mode === 'upload' && (
            <div className="tab-panel" key="upload">
              <DropZone file={file} setFile={setFile} />
            </div>
          )}

          {mode === 'manual' && (
            <div className="tab-panel" key="manual">
              <textarea
                className="field-area"
                placeholder="Paste submissions, one per line, or as JSON, or as free text — the court will sort it out."
                value={manual}
                onChange={(e) => setManual(e.target.value)}
                autoFocus
              />
              <div className="scrape-hint">
                {manual.split('\n').filter(Boolean).length} lines · {manual.length} chars
              </div>
            </div>
          )}
        </section>

        <div style={{ marginTop: 56 }}>
          <ModelPicker models={models} reasoning={modelReasoning} setReasoning={setModelReasoning} fast={modelFast} setFast={setModelFast} limit={limit} setLimit={setLimit} />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <button className="door" type="submit" disabled={uploading}>
            {uploading ? 'UPLOADING…' : 'PASS JUDGMENT'} <span className="arrow">→</span>
          </button>
          <span className="serif-italic" style={{ fontSize: 16, color: 'var(--ink-dim)' }}>
            The bench is summoned. The court will rule.
          </span>
        </div>
      </form>
    </div>
  );
}

function DropZone({ file, setFile }) {
  const [drag, setDrag] = React.useState(false);
  const inputRef = React.useRef(null);

  const onChoose = () => inputRef.current && inputRef.current.click();
  const onDrop = (e) => {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) setFile(f);
  };

  return (
    <div
      className={`dropzone ${drag ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
      onClick={onChoose}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
    >
      {file ? (
        <>
          <div className="main">✓ {file.name}</div>
          <div className="sub">{(file.size / 1024).toFixed(1)} kb · click to replace</div>
        </>
      ) : (
        <>
          <div className="main">Drop a file containing the submissions.</div>
          <div className="sub">accepted: .csv .json .md .txt .pdf</div>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.json,.md,.txt,.pdf"
        style={{ display: 'none' }}
        onChange={(e) => { const f = e.target.files && e.target.files[0]; if (f) setFile(f); }}
      />
    </div>
  );
}

// ─── Deliberating ─────────────────────────────────────────────────────────────

function JudgmentDeliberating({ traces, flash }) {
  return (
    <div className="wrap fade-in" style={{ paddingTop: 160, paddingBottom: 120 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: 80, alignItems: 'center', minHeight: '60vh' }}>
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <Sigil size={320} spinning flash={flash} />
        </div>
        <div style={{ minHeight: 360, paddingTop: 20 }}>
          <div className="section-label" style={{ marginBottom: 28 }}>DELIBERATING</div>
          <TraceStream lines={traces} />
        </div>
      </div>
    </div>
  );
}

// ─── Ruling / leaderboard ─────────────────────────────────────────────────────

function JudgmentRuling({ report, verdictId }) {
  const r = report || {};
  const id = verdictId || r.id || 'judgment-r0091';
  return (
    <div style={{ paddingTop: 100, paddingBottom: 80 }} className="fade-in-slow">
      <BenchBody r={r} showShare id={id} />
    </div>
  );
}

function BenchBody({ r, showShare, id, permalink = false }) {
  // Normalise criteria — backend may use 'rubric' or 'criteria'
  const criteria = r.criteria || (r.rubric || []).map((c) => ({
    key: (c.criterion || c.name || '').toLowerCase().replace(/\s+/g, '_'),
    name: c.criterion || c.name || '',
    weight: c.weight || 0,
  }));

  const bench = r.bench || r.leaderboard || [];

  return (
    <div className="wrap-wide">
      <header className="ruling-head">
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8 }}>
          <Sigil size={84} />
        </div>
        <div className="title">THE RULING</div>
        <div className="sub">
          {permalink && <>CASE Nº {(id || '').toUpperCase()} · </>}
          <span className="gold">{r.count || bench.length}</span> SUBMISSIONS JUDGED · RULED AT <span className="gold">{r.ts || '—'}</span>
        </div>
        <div className="serif-italic" style={{ marginTop: 22, fontSize: 18, color: 'var(--ink-dim)' }}>
          {r.field || 'The Bench'}
        </div>
      </header>

      {criteria.length > 0 && <CriteriaChips criteria={criteria} />}

      {r.summary && (
        <div style={{ marginBottom: 48, padding: '32px 40px', border: '1px solid var(--rule)', background: 'var(--gold-faint)' }}>
          <div className="section-label" style={{ marginBottom: 16 }}>THE COURT'S OPINION</div>
          <p style={{ fontFamily: 'var(--serif)', fontSize: 20, lineHeight: 1.6, color: 'var(--ink-dim)', fontStyle: 'italic' }}>
            {r.summary}
          </p>
        </div>
      )}

      <section style={{ marginBottom: 64 }}>
        <div className="section-label" style={{ marginBottom: 28, textAlign: 'center' }}>─── THE BENCH ───</div>
        <div className="bench">
          {bench.map((entry, i) => (
            <BenchRow
              key={entry.name || i}
              entry={entry}
              criteria={criteria}
              isWinner={i === 0}
              isLast={i === bench.length - 1}
              defaultOpen={i === 0}
            />
          ))}
        </div>
        {bench.length > 0 && (
          <div className="bench-last-line">— the court is unmoved.</div>
        )}
      </section>

      {showShare && id && (
        <>
          <hr className="rule" />
          <div style={{ display: 'flex', justifyContent: 'center', paddingBottom: 40 }}>
            <ShareRow id={id} />
          </div>
        </>
      )}
      {r.models_used && (
        <div style={{ textAlign: 'center', paddingBottom: 40, fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '0.3em', color: 'var(--ink-faint)', opacity: 0.7 }}>
          ruled by {r.models_used.reasoning} · executed by {r.models_used.fast}
        </div>
      )}
    </div>
  );
}

function CriteriaChips({ criteria }) {
  return (
    <div className="criteria-chips">
      {criteria.map((c) => (
        <span key={c.key} className="criteria-chip">
          {c.name} <span className="weight">{c.weight}%</span>
        </span>
      ))}
    </div>
  );
}

function BenchRow({ entry, criteria, isWinner, isLast, defaultOpen = false }) {
  const [open, setOpen]     = React.useState(defaultOpen);
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    const t = setTimeout(() => setMounted(true), 120);
    return () => clearTimeout(t);
  }, []);

  // Normalise scores — backend uses rubric_scores array, mock uses scores dict
  const scoresDict = React.useMemo(() => {
    if (entry.scores) return entry.scores;
    if (entry.rubric_scores) {
      return Object.fromEntries(
        entry.rubric_scores.map((rs) => [
          (rs.criterion || '').toLowerCase().replace(/\s+/g, '_'),
          rs.score,
        ])
      );
    }
    return {};
  }, [entry]);

  const notesDict = React.useMemo(() => {
    if (entry.notes) return entry.notes;
    if (entry.rubric_scores) {
      return Object.fromEntries(
        entry.rubric_scores.map((rs) => [
          (rs.criterion || '').toLowerCase().replace(/\s+/g, '_'),
          rs.note || '',
        ])
      );
    }
    return {};
  }, [entry]);

  const cls = ['bench-row', isWinner && 'is-winner', isLast && 'is-last', open && 'is-expanded'].filter(Boolean).join(' ');

  return (
    <article className={cls} onClick={() => setOpen(!open)} role="button" aria-expanded={open}>
      <div className="bench-rank">{String(entry.rank || '?').padStart(2, '0')}</div>

      <div className="bench-mid">
        <div className="bench-name">{entry.name || entry.title || ''}</div>
        <div className="bench-team">by {entry.team || ''}</div>
      </div>

      <div className="bench-bars">
        {criteria.map((c) => {
          const got = scoresDict[c.key] || 0;
          const pct = mounted ? Math.max(0, Math.min(100, (got / (c.weight || 1)) * 100)) : 0;
          return (
            <div className="bench-mini" key={c.key}>
              <div className="bench-mini-label">{c.name}</div>
              <div className="bench-mini-track">
                <div className="bench-mini-fill" style={{ width: `${pct}%`, transitionDelay: `${(entry.rank || 1) * 80}ms` }} />
              </div>
            </div>
          );
        })}
      </div>

      <div className="bench-score">
        <div className="num">{entry.total ?? entry.overall_score ?? '—'}</div>
        <div className="of">/ 100</div>
      </div>

      <div className="bench-chev" aria-hidden="true">▾</div>

      {open && (
        <div className="bench-expand" onClick={(e) => e.stopPropagation()}>
          {(entry.ai || entry.ai_description) && (
            <div className="b-ai">{entry.ai || entry.ai_description}</div>
          )}
          {(entry.verdict || entry.verdict_line) && (
            <div className="b-verdict">"{entry.verdict || entry.verdict_line}"</div>
          )}

          <div className="b-notes">
            {criteria.map((c) => {
              const got  = scoresDict[c.key] || 0;
              const note = notesDict[c.key] || '';
              return (
                <div className="b-note" key={c.key}>
                  <div className="row">
                    <span className="name">{c.name}</span>
                    <span className="score">{got}<span className="max">/{c.weight}</span></span>
                  </div>
                  {note && <div className="note">"{note}"</div>}
                </div>
              );
            })}
          </div>

          <div className="b-footrow">
            <div style={{ display: 'flex', gap: 18, alignItems: 'center', flexWrap: 'wrap' }}>
              <ProjectLinks links={entry.links} />
              <TrackChips tracks={entry.tracks} />
            </div>
            {isWinner && entry.spoken && <SpeakButton text={entry.spoken} compact />}
          </div>
        </div>
      )}
    </article>
  );
}

function SpeakButton({ text, compact }) {
  const [playing, setPlaying] = React.useState(false);
  React.useEffect(() => () => { try { window.speechSynthesis.cancel(); } catch (e) {} }, []);
  const toggle = () => {
    if (!('speechSynthesis' in window)) { alert('The court regrets: this browser does not speak.'); return; }
    if (playing) { window.speechSynthesis.cancel(); setPlaying(false); return; }
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 0.92; u.pitch = 0.85;
    u.onend = () => setPlaying(false);
    u.onerror = () => setPlaying(false);
    window.speechSynthesis.speak(u);
    setPlaying(true);
  };
  return (
    <button
      className={`btn-speak ${playing ? 'is-playing' : ''}`}
      onClick={toggle}
      style={compact ? { padding: '12px 22px', fontSize: 13 } : null}
    >
      <span className="tri" />
      {playing ? 'SILENCE' : 'SPEAK THE RULING'}
    </button>
  );
}

// ───────── PAGE 4 — /v/<id> ───────────────────────────────────────────────────
function Permalink({ id }) {
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);

  // Try real API first; fall back to mock
  React.useEffect(() => {
    if (!id) { setLoading(false); return; }
    fetch(`/api/verdict/${id}`)
      .then((r) => r.ok ? r.json() : Promise.reject())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => {
        // Fall back to mock based on id prefix
        if (id.startsWith('scout')) setData({ ...MOCK.SCOUT_REPORT, type: 'scout', id });
        else setData({ ...MOCK.JUDGMENT_RULING, type: 'judgment', id });
        setLoading(false);
      });
  }, [id]);

  if (loading) {
    return (
      <div className="route" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div style={{ textAlign: 'center' }}>
          <Sigil size={80} spinning />
          <div className="section-label" style={{ marginTop: 24 }}>RETRIEVING THE RECORD…</div>
        </div>
      </div>
    );
  }

  const isScout = data && data.type === 'scout';
  const ts = (data && (data.ts || data.created_at)) || '—';

  return (
    <div className="route" data-screen-label={`04 Permalink — ${id}`}>
      <div className="topbar-bg" />
      <TopBar meta={`permalink · ${id}`} />

      {isScout ? (
        <>
          <div style={{ paddingTop: 140, paddingBottom: 40, textAlign: 'center' }} className="fade-in">
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 28 }}>
              <Sigil size={120} />
            </div>
            <div className="wordmark" style={{ fontSize: 22, marginBottom: 12 }}>VERDICT</div>
            <div className="serif-italic" style={{ fontSize: 16, color: 'var(--ink-dim)' }}>A ruling on the field.</div>
          </div>
          <div className="fade-in fade-in-delay-1">
            <PermalinkScout r={data} id={id} />
          </div>
        </>
      ) : (
        <div className="fade-in" style={{ paddingTop: 100, paddingBottom: 40 }}>
          <BenchBody r={data || MOCK.JUDGMENT_RULING} permalink id={id} />
        </div>
      )}

      <div className="permalink-foot fade-in fade-in-delay-2">
        Verdict delivered at <span style={{ color: 'var(--ink)' }}>{ts}</span>.
        &nbsp;
        <a href={isScout ? '/judgment' : '/scout'} onClick={(e) => { e.preventDefault(); window.nav(isScout ? '/judgment' : '/scout'); }}>
          {isScout ? 'Pass judgment yourself →' : 'Read the room →'}
        </a>
      </div>
      {data && data.models_used && (
        <div style={{ textAlign: 'center', paddingBottom: 40, fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '0.3em', color: 'var(--ink-faint)', opacity: 0.7 }}>
          ruled by {data.models_used.reasoning} · executed by {data.models_used.fast}
        </div>
      )}
    </div>
  );
}

function PermalinkScout({ r, id }) {
  const gaps = Array.isArray(r.gaps) ? r.gaps : [];
  const fav  = r.favorite || {};

  let clusterArr = [];
  if (Array.isArray(r.clusters)) {
    clusterArr = r.clusters;
  } else if (r.clusters) {
    const projects = r.projects || [];
    clusterArr = Object.entries(r.clusters).map(([cid, c]) => ({
      id: cid, label: c.label || cid, nodes: projects.filter((p) => p.cluster === cid),
    }));
  }

  return (
    <div className="wrap-wide">
      <div style={{ textAlign: 'center', marginBottom: 80 }}>
        <div className="section-label" style={{ marginBottom: 14 }}>CASE Nº {(id || '').toUpperCase()} · IN RE:</div>
        <h1 className="h-1" style={{ marginBottom: 8 }}>{r.field || 'The Field'}</h1>
        <div className="serif-italic" style={{ fontSize: 18, color: 'var(--ink-dim)' }}>
          The court reviewed {r.count || '?'} briefs.
        </div>
      </div>

      {clusterArr.length > 0 && (
        <section style={{ marginBottom: 96 }}>
          <div className="section-label" style={{ marginBottom: 20 }}>I. THE FIELD</div>
          <NodeField clusters={clusterArr} />
          <div style={{ marginTop: 56 }}><FieldClusters clusters={clusterArr} /></div>
        </section>
      )}

      {gaps.length > 0 && (
        <section style={{ marginBottom: 96 }}>
          <div className="section-label" style={{ marginBottom: 20 }}>II. THE GAPS</div>
          <div style={{ display: 'grid', gap: 18 }}>
            {gaps.map((g, i) => (
              <div key={i} className="gap-card">
                <span className="num">GAP {String(i + 1).padStart(2, '0')}</span>
                {typeof g === 'string' ? g : g.headline}
              </div>
            ))}
          </div>
        </section>
      )}

      {(fav.name || fav.project_id) && (
        <section style={{ marginBottom: 60 }}>
          <div className="section-label" style={{ marginBottom: 20 }}>III. THE COURT'S FAVORITE</div>
          <div className="favorite-card">
            <div className="stamp"><Sigil size={64} /></div>
            <div className="verdict-label">— DARK HORSE OF THE FIELD —</div>
            <div className="name">{fav.name || fav.title || ''}</div>
            <div className="pc-team" style={{ textAlign: 'center' }}>by {fav.team || ''}</div>
            <hr className="rule-short" style={{ marginBottom: 24 }} />
            <p className="pc-ai">{fav.ai || fav.ai_description || ''}</p>
            <ProjectLinks links={fav.links} center />
            <TrackChips tracks={fav.tracks} center />
            <p className="reason" style={{ marginTop: 18 }}>{fav.reason || fav.reasoning || ''}</p>
          </div>
        </section>
      )}
    </div>
  );
}

Object.assign(window, {
  Judgment, JudgmentInput, JudgmentDeliberating, JudgmentRuling,
  BenchBody, BenchRow, CriteriaChips, DropZone, SpeakButton,
  Permalink, PermalinkScout,
});
