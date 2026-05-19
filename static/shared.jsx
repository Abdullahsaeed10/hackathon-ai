// Shared chrome — topbar, trace stream, project cards, link icons.

function TopBar({ meta }) {
  return (
    <div className="topbar fade-in">
      <a href="#/" className="topbar-brand" onClick={(e) => { e.preventDefault(); window.nav('/'); }}>
        <Sigil size={32} />
        <span className="wm-small">VERDICT</span>
      </a>
      <div className="topbar-meta">
        <span className="dot" />
        {meta || 'the court is in session'}
      </div>
    </div>
  );
}

// ── Mock trace (used when backend is offline) ────────────────────────────────

function useTrace(lines, { speed = 700, autostart = false } = {}) {
  const [shown, setShown] = React.useState(autostart ? 0 : -1);
  const [done, setDone]   = React.useState(false);

  React.useEffect(() => {
    if (shown < 0) return;
    if (shown >= lines.length) { setDone(true); return; }
    const t = setTimeout(() => setShown((s) => s + 1), speed);
    return () => clearTimeout(t);
  }, [shown, lines, speed]);

  const start = () => { setShown(0); setDone(false); };
  return { shown, done, start, visible: lines.slice(0, Math.max(shown, 0)) };
}

// ── Real SSE fetch (POST → ReadableStream) ───────────────────────────────────

function useSSEFetch({ endpoint, body, onTrace, onFinal, onError, enabled }) {
  React.useEffect(() => {
    if (!enabled) return;
    let cancelled = false;

    (async () => {
      try {
        const resp = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });

        if (!resp.ok) {
          onError && onError(`Server returned ${resp.status}`);
          return;
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buf = '';

        while (!cancelled) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          // SSE events are separated by double newline
          const parts = buf.split('\n\n');
          buf = parts.pop() || '';
          for (const part of parts) {
            const dataLine = part.split('\n').find((l) => l.startsWith('data: '));
            if (!dataLine) continue;
            try {
              const ev = JSON.parse(dataLine.slice(6));
              if (ev.type === 'thought' || ev.type === 'tool_call' || ev.type === 'tool_result') {
                const text = ev.text || (ev.type === 'tool_call' ? `${ev.tool}: ${ev.args_summary || '…'}` : `${ev.tool}: ${ev.summary || '…'}`);
                onTrace && onTrace(text);
              } else if (ev.type === 'final') {
                onFinal && onFinal(ev);
              } else if (ev.type === 'error') {
                onError && onError(ev.message || 'unknown error');
              }
            } catch (_) {}
          }
        }
      } catch (err) {
        if (!cancelled) onError && onError(err.message);
      }
    })();

    return () => { cancelled = true; };
  }, [enabled]);
}

// ── TraceStream display ──────────────────────────────────────────────────────

function TraceStream({ lines }) {
  const total = lines.length;
  return (
    <div>
      {lines.map((l, i) => {
        const fromEnd = total - 1 - i;
        const cls = fromEnd === 0 ? 'latest' : fromEnd === 1 ? 'prev-1' : fromEnd === 2 ? 'prev-2' : fromEnd === 3 ? 'prev-3' : 'prev-4';
        return (
          <div key={i} className={`trace-line ${cls} ${fromEnd === 0 ? 'caret' : ''}`}>
            → {l}
          </div>
        );
      })}
    </div>
  );
}

// ── Link icons ───────────────────────────────────────────────────────────────

const IconCode = () => (
  <svg viewBox="0 0 16 16" aria-hidden="true">
    <path d="M5.5 4 L2.5 8 L5.5 12" stroke="currentColor" fill="none" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M10.5 4 L13.5 8 L10.5 12" stroke="currentColor" fill="none" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const IconLink = () => (
  <svg viewBox="0 0 16 16" aria-hidden="true">
    <path d="M3 5 L3 13 L11 13 L11 9" stroke="currentColor" fill="none" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M9 3 L13 3 L13 7" stroke="currentColor" fill="none" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M13 3 L7 9" stroke="currentColor" fill="none" strokeWidth="1.4" strokeLinecap="round" />
  </svg>
);
const IconPlay = () => (
  <svg viewBox="0 0 16 16" aria-hidden="true">
    <polygon points="5,3 5,13 13,8" fill="currentColor" />
  </svg>
);
const IconDoc = () => (
  <svg viewBox="0 0 16 16" aria-hidden="true">
    <path d="M3.5 2.5 L10 2.5 L12.5 5 L12.5 13.5 L3.5 13.5 Z" stroke="currentColor" fill="none" strokeWidth="1.3" strokeLinejoin="round" />
    <path d="M10 2.5 L10 5 L12.5 5" stroke="currentColor" fill="none" strokeWidth="1.3" strokeLinejoin="round" />
    <line x1="5.5" y1="8"    x2="10.5" y2="8"    stroke="currentColor" strokeWidth="1" />
    <line x1="5.5" y1="10.5" x2="10.5" y2="10.5" stroke="currentColor" strokeWidth="1" />
  </svg>
);

const LINK_ORDER = [
  { key: 'github',     label: 'CODE',       icon: IconCode },
  { key: 'demo',       label: 'LIVE DEMO',  icon: IconLink },
  { key: 'video',      label: 'VIDEO',      icon: IconPlay },
  { key: 'submission', label: 'SUBMISSION', icon: IconDoc },
];

function ProjectLinks({ links, center = false }) {
  if (!links) return null;
  const items = LINK_ORDER.filter((l) => links[l.key]);
  if (items.length === 0) return null;
  return (
    <div className="pc-links" style={center ? { justifyContent: 'center' } : null}>
      {items.map(({ key, label, icon: Icon }) => (
        <a
          key={key}
          href={links[key]}
          className="pc-link"
          title={label}
          aria-label={label}
          onClick={(e) => { if (!links[key] || links[key] === '#') e.preventDefault(); }}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Icon />
        </a>
      ))}
    </div>
  );
}

function TrackChips({ tracks, center = false }) {
  if (!tracks || tracks.length === 0) return null;
  return (
    <div className="pc-tracks" style={center ? { justifyContent: 'center' } : null}>
      {tracks.map((t, i) => <span key={i} className="pc-track">{t}</span>)}
    </div>
  );
}

function ProjectCard({ p }) {
  const name = p.name || p.title || '';
  const ai   = p.ai || p.ai_description || '';
  const v    = p.verdict || p.verdict_line || '';
  return (
    <article className="project-card">
      <h3 className="pc-title">{name}</h3>
      <div className="pc-team">by {p.team}</div>
      {ai && <p className="pc-ai">{ai}</p>}
      <ProjectLinks links={p.links} />
      <TrackChips tracks={p.tracks} />
      {v && <div className="pc-verdict">"{v}"</div>}
    </article>
  );
}

function FieldClusters({ clusters }) {
  // Accepts either an array (design mock format) or a dict (backend format).
  let clusterList = [];
  if (Array.isArray(clusters)) {
    clusterList = clusters;
  } else if (clusters && typeof clusters === 'object') {
    clusterList = Object.entries(clusters).map(([id, c]) => ({
      id,
      label: c.label || id,
      nodes: c.nodes || c.projects || [],
    }));
  }

  return (
    <div className="field-clusters">
      {clusterList.map((c) => (
        <section key={c.id} className="field-cluster">
          <header className="field-cluster-head">
            <span className="label">{c.label}</span>
            <span className="count">n = {(c.nodes || []).length}</span>
            <div className="rule-v" />
          </header>
          <div className="field-cluster-grid">
            {(c.nodes || []).map((n, i) => <ProjectCard key={i} p={n} />)}
          </div>
        </section>
      ))}
    </div>
  );
}

// ── Share row ────────────────────────────────────────────────────────────────

function ShareRow({ id }) {
  const [toast, setToast] = React.useState(false);
  const share = () => {
    const url = `${location.origin}/v/${id}`;
    try { navigator.clipboard.writeText(url); } catch (e) {}
    setToast(true);
    setTimeout(() => setToast(false), 1800);
  };
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 28, marginTop: 24 }}>
      <button className="door" onClick={share}>
        SHARE THIS RULING <span className="arrow">→</span>
      </button>
      <a
        href={`/v/${id}`}
        onClick={(e) => { e.preventDefault(); window.nav(`/v/${id}`); }}
        className="serif-italic"
        style={{ fontSize: 16, color: 'var(--ink-dim)', textDecoration: 'none', borderBottom: '1px dotted var(--ink-faint)', paddingBottom: 2 }}
      >
        view the permalink →
      </a>
      {toast && <div className="toast">link copied · /v/{id}</div>}
    </div>
  );
}

// ── Model picker ─────────────────────────────────────────────────────────────

function useModels() {
  const [models, setModels] = React.useState([
    { name: 'gemini-2.5-pro',   display_name: 'Gemini 2.5 Pro',   recommended_for: 'reasoning' },
    { name: 'gemini-2.5-flash', display_name: 'Gemini 2.5 Flash', recommended_for: 'fast' },
  ]);

  React.useEffect(() => {
    fetch('/api/models')
      .then((r) => r.ok ? r.json() : Promise.reject())
      .then((d) => { if ((d.models || []).length > 0) setModels(d.models); })
      .catch(() => {});
  }, []);

  const defaultReasoning = (models.find((m) => m.recommended_for === 'reasoning') || models[0] || {}).name || 'gemini-2.5-pro';
  const defaultFast      = (models.find((m) => m.recommended_for === 'fast')      || models[1] || {}).name || 'gemini-2.5-flash';

  return { models, defaultReasoning, defaultFast };
}

const LIMIT_PRESETS = [
  { label: 'TOP 5',  value: 5   },
  { label: 'TOP 10', value: 10  },
  { label: 'TOP 25', value: 25  },
  { label: 'ALL',    value: null },
];

function LimitPicker({ limit, setLimit }) {
  return (
    <div style={{ marginBottom: 32 }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '0.4em', textTransform: 'uppercase', color: 'var(--ink-faint)', marginBottom: 12 }}>
        HOW MANY TO RULE ON
      </div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        {LIMIT_PRESETS.map((p) => {
          const active = limit === p.value;
          return (
            <button
              key={p.label}
              type="button"
              onClick={() => setLimit(p.value)}
              style={{
                fontFamily: 'var(--mono)',
                fontSize: 11,
                letterSpacing: '0.25em',
                textTransform: 'uppercase',
                padding: '6px 16px',
                border: `1px solid ${active ? 'var(--gold)' : 'var(--rule)'}`,
                background: active ? 'var(--gold-faint)' : 'transparent',
                color: active ? 'var(--gold)' : 'var(--ink-faint)',
                cursor: 'pointer',
                boxShadow: active ? '0 0 14px var(--gold-glow)' : 'none',
                transition: 'all 300ms ease',
              }}
            >
              {p.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ModelPicker({ models, reasoning, setReasoning, fast, setFast, limit, setLimit }) {
  return (
    <section style={{ marginBottom: 56 }}>
      <div className="rules-field-label">— THE COURT'S MIND —</div>
      <div style={{ marginTop: 6, marginBottom: 24, fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '0.3em', textTransform: 'uppercase', color: 'var(--ink-faint)', fontStyle: 'italic' }}>
        choose whose voice rules
      </div>
      <LimitPicker limit={limit} setLimit={setLimit} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 40, maxWidth: 680 }}>
        <ModelSelect label="REASONING" value={reasoning} onChange={setReasoning} models={models} />
        <ModelSelect label="EXECUTION" value={fast}      onChange={setFast}      models={models} />
      </div>
    </section>
  );
}

function ModelSelect({ label, value, onChange, models }) {
  return (
    <div>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '0.4em', textTransform: 'uppercase', color: 'var(--ink-faint)', marginBottom: 10 }}>
        {label}
      </div>
      <select
        className="field-line model-select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {models.map((m) => (
          <option key={m.name} value={m.name}>
            {m.display_name}{m.recommended_for ? ' ★' : ''}
          </option>
        ))}
      </select>
    </div>
  );
}

Object.assign(window, {
  TopBar, useTrace, useSSEFetch, TraceStream,
  IconCode, IconLink, IconPlay, IconDoc,
  ProjectLinks, TrackChips, ProjectCard, FieldClusters,
  ShareRow, useModels, ModelPicker, ModelSelect, LimitPicker,
});
