// ───────── PAGE 1 — / (Landing) ──────────────────────────────────────────────
function Landing() {
  return (
    <div className="route" data-screen-label="01 Landing">
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'space-between', padding: '120px 24px 80px', textAlign: 'center' }}>

        <div className="center-col" style={{ flex: 1, justifyContent: 'center', display: 'flex', gap: 0 }}>
          <div className="fade-in-slow" style={{ marginBottom: 64 }}>
            <Sigil size={260} />
          </div>
          <div className="fade-in fade-in-delay-2">
            <div className="wordmark" style={{ fontSize: 38 }}>VERDICT</div>
          </div>
          <div className="fade-in fade-in-delay-3" style={{ marginTop: 28 }}>
            <div className="serif-italic" style={{ fontSize: 22 }}>The court is in session.</div>
          </div>
        </div>

        <div className="fade-in fade-in-delay-4" style={{ display: 'flex', gap: 32, flexWrap: 'wrap', justifyContent: 'center', marginTop: 80 }}>
          <a className="door" href="/scout" onClick={(e) => { e.preventDefault(); window.nav('/scout'); }}>
            READ THE ROOM <span className="arrow">→</span>
          </a>
          <a className="door" href="/judgment" onClick={(e) => { e.preventDefault(); window.nav('/judgment'); }}>
            PASS JUDGMENT <span className="arrow">→</span>
          </a>
        </div>

        <div className="fade-in fade-in-delay-4" style={{ marginTop: 64, fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '0.4em', color: 'var(--ink-faint)', textTransform: 'uppercase' }}>
          · est. 2026 · case nº 0047 · in re: the field ·
        </div>
      </div>
    </div>
  );
}

// ───────── PAGE 2 — /scout ────────────────────────────────────────────────────
function Scout() {
  const [phase, setPhase]       = React.useState('input');
  const [url, setUrl]           = React.useState('');
  const [traces, setTraces]     = React.useState([]);
  const [flash, setFlash]       = React.useState(0);
  const [report, setReport]     = React.useState(null);
  const [verdictId, setVerdictId] = React.useState(null);
  const [inputError, setInputError] = React.useState(null);
  const [useReal, setUseReal]   = React.useState(false);

  const { models, defaultReasoning, defaultFast } = useModels();
  const [modelReasoning, setModelReasoning] = React.useState('');
  const [modelFast, setModelFast]           = React.useState('');
  const [limit, setLimit]                   = React.useState(null);
  React.useEffect(() => { if (!modelReasoning) setModelReasoning(defaultReasoning); }, [defaultReasoning]);
  React.useEffect(() => { if (!modelFast)      setModelFast(defaultFast);           }, [defaultFast]);

  // Pulse sigil on each new trace line
  React.useEffect(() => {
    if (phase === 'deliberating') setFlash((f) => f + 1);
  }, [traces.length]);

  // Real SSE
  useSSEFetch({
    endpoint: '/api/scout',
    body: { url, model_reasoning: modelReasoning, model_fast: modelFast, limit },
    enabled: useReal && phase === 'deliberating',
    onTrace: (text) => setTraces((t) => [...t, text]),
    onFinal: (ev) => {
      setVerdictId(ev.verdict_id);
      setReport(ev.report);
      setPhase('ruling');
    },
    onError: (msg) => {
      setUseReal(false);
      setPhase('input');
      setInputError(msg);
    },
  });

  const submit = async (e) => {
    e && e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) {
      setInputError('Please provide a hackathon link to proceed.');
      return;
    }
    setInputError(null);
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
      setTraces((t) => [...t, `Found ${result.submission_count} submission(s) — starting analysis…`]);
      setUseReal(true);
    } catch {
      // Validation endpoint unreachable — proceed anyway; SSE will surface any real errors.
      setTraces((t) => [...t, 'Proceeding to analysis…']);
      setUseReal(true);
    }
  };

  const visibleTraces = traces;

  return (
    <div className="route" data-screen-label={`02 Scout — ${phase}`}>
      <div className="topbar-bg" />
      <TopBar meta={phase === 'input' ? 'awaiting the field' : phase === 'deliberating' ? 'deliberating' : 'ruling rendered'} />

      {phase === 'input'       && <ScoutInput url={url} setUrl={setUrl} submit={submit} models={models} modelReasoning={modelReasoning} setModelReasoning={setModelReasoning} modelFast={modelFast} setModelFast={setModelFast} limit={limit} setLimit={setLimit} inputError={inputError} />}
      {phase === 'deliberating'&& <ScoutDeliberating traces={visibleTraces} flash={flash} />}
      {phase === 'ruling'      && <ScoutRuling report={report} verdictId={verdictId} traces={traces} />}
    </div>
  );
}

function ScoutInput({ url, setUrl, submit, models, modelReasoning, setModelReasoning, modelFast, setModelFast, limit, setLimit, inputError }) {
  return (
    <div className="wrap fade-in" style={{ paddingTop: 220, paddingBottom: 120 }}>
      <div className="section-label fade-in fade-in-delay-1" style={{ marginBottom: 28 }}>I. READ THE ROOM</div>
      <h1 className="h-display fade-in fade-in-delay-1" style={{ marginBottom: 80, maxWidth: 920 }}>
        Name the <em>field.</em>
      </h1>
      <form onSubmit={submit} className="fade-in fade-in-delay-2" style={{ maxWidth: 880 }}>
        <input
          className={`field-line${inputError ? ' field-error' : ''}`}
          type="text"
          placeholder="https://lablab.ai/event/… or devpost.com/…"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          autoFocus
        />
        {inputError && (
          <div className="field-error-msg">{inputError}</div>
        )}
        <div style={{ marginTop: 18, fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.3em', textTransform: 'uppercase', color: 'var(--ink-faint)' }}>
          lablab.ai · devpost · lu.ma · hackathon.com
        </div>
        <div style={{ marginTop: 64, marginBottom: 0 }}>
          <ModelPicker models={models} reasoning={modelReasoning} setReasoning={setModelReasoning} fast={modelFast} setFast={setModelFast} limit={limit} setLimit={setLimit} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <button className="door" type="submit">
            DELIVER <span className="arrow">→</span>
          </button>
          <span className="serif-italic" style={{ fontSize: 16 }}>The court will read every brief.</span>
        </div>
      </form>
    </div>
  );
}

function ScoutDeliberating({ traces, flash }) {
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

function ScoutRuling({ report, verdictId, traces }) {
  const r = report || {};
  const id = verdictId || 'scout-0047';

  // Normalise clusters to array form for rendering
  let clusterArr = [];
  if (Array.isArray(r.clusters)) {
    clusterArr = r.clusters;
  } else if (r.clusters && typeof r.clusters === 'object') {
    // Backend returns {cid: {label, project_ids}} — build from projects
    const projects = r.projects || [];
    clusterArr = Object.entries(r.clusters).map(([cid, c]) => ({
      id: cid,
      label: c.label || cid,
      nodes: projects.filter((p) => p.cluster === cid),
    }));
  }

  const gaps = Array.isArray(r.gaps) ? r.gaps : [];
  const fav  = r.favorite || {};

  return (
    <div style={{ paddingTop: 120, paddingBottom: 120 }} className="fade-in-slow">
      <div className="wrap-wide" style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 64 }}>
        {/* trace rail */}
        <aside className="trace-rail">
          <div className="section-label" style={{ marginBottom: 22 }}>RECORD OF PROCEEDINGS</div>
          {(traces || []).map((l, i) => (
            <div key={i} className="trace-line prev-1" style={{ whiteSpace: 'normal', lineHeight: 1.7, marginBottom: 2 }}>→ {l}</div>
          ))}
          <div style={{ marginTop: 28, paddingTop: 22, borderTop: '1px solid var(--rule)', fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '0.3em', color: 'var(--gold)', textTransform: 'uppercase' }}>
            ✓ verdict rendered
            <div style={{ marginTop: 8, color: 'var(--ink-faint)', letterSpacing: '0.2em' }}>
              {r.count || '?'} submissions reviewed
            </div>
          </div>
        </aside>

        <main>
          <div style={{ marginBottom: 64 }}>
            <div className="section-label" style={{ marginBottom: 14 }}>IN RE:</div>
            <h1 className="h-1" style={{ marginBottom: 6 }}>{r.field || 'The Field'}</h1>
            <div className="serif-italic" style={{ fontSize: 18 }}>
              The court, having reviewed {r.count || '?'} briefs, rules as follows.
            </div>
          </div>

          {/* THE FIELD */}
          <section style={{ marginBottom: 96 }}>
            <div className="section-label" style={{ marginBottom: 20 }}>I. THE FIELD</div>
            <p className="serif-italic" style={{ fontSize: 18, color: 'var(--ink-dim)', marginBottom: 28, maxWidth: 720 }}>
              {clusterArr.length} clusters identified. The map first; then the briefs.
            </p>
            {clusterArr.length > 0 && <NodeField clusters={clusterArr} />}
            <div style={{ marginTop: 56 }}>
              <FieldClusters clusters={clusterArr} />
            </div>
          </section>

          {/* THE GAPS */}
          {gaps.length > 0 && (
            <section style={{ marginBottom: 96 }}>
              <div className="section-label" style={{ marginBottom: 20 }}>II. THE GAPS</div>
              <p className="serif-italic" style={{ fontSize: 18, color: 'var(--ink-dim)', marginBottom: 28, maxWidth: 720 }}>
                What the field, in its haste, has failed to imagine.
              </p>
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

          {/* THE FAVORITE */}
          {(fav.name || fav.project_id) && (
            <section style={{ marginBottom: 80 }}>
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

          <ShareRow id={id} />
        </main>
      </div>
    </div>
  );
}

// ── Node field — pre-computed percentage positions ───────────────────────────

function NodeField({ clusters }) {
  return (
    <div className="node-field">
      {clusters.map((c) => {
        const cx = c.x ?? Math.random() * 80 + 10;
        const cy = c.y ?? Math.random() * 70 + 10;
        return (
          <div key={c.id} className="cluster-label" style={{ left: `${cx}%`, top: `${cy - 12}%` }}>
            {c.label}
          </div>
        );
      })}
      {clusters.flatMap((c) =>
        (c.nodes || []).map((n, i) => {
          const nx = n.x ?? (c.x ?? 50) + (Math.random() * 20 - 10);
          const ny = n.y ?? (c.y ?? 50) + (Math.random() * 20 - 10);
          return (
            <div key={`${c.id}-${i}`} className="node" style={{ left: `${nx}%`, top: `${ny}%` }}>
              <div className="node-dot" />
              <div className="node-label">{n.name || n.title}</div>
              <div className="node-tip">{n.verdict || n.verdict_line}</div>
            </div>
          );
        })
      )}
    </div>
  );
}

Object.assign(window, { Landing, Scout, NodeField });
