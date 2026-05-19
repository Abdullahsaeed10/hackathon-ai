// Sigil — the soul of the app. Concentric rings + center mark + slow rotation.
function Sigil({ size = 200, spinning = false, flash = 0, className = '' }) {
  const ref = React.useRef(null);

  React.useEffect(() => {
    if (!flash || !ref.current) return;
    const el = ref.current;
    el.classList.remove('flash');
    void el.offsetWidth;
    el.classList.add('flash');
  }, [flash]);

  return (
    <div
      ref={ref}
      className={`sigil ${spinning ? 'is-spinning' : ''} ${className}`}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <svg viewBox="-100 -100 200 200">
        <defs>
          <radialGradient id="sg-core" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stopColor="#D4A53A" stopOpacity="0.9" />
            <stop offset="60%"  stopColor="#D4A53A" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#D4A53A" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* outer ring with tick marks */}
        <g className="ring-outer">
          <circle cx="0" cy="0" r="92" fill="none" stroke="currentColor" strokeWidth="0.6" opacity="0.55" />
          {Array.from({ length: 48 }).map((_, i) => {
            const a = (i * 360) / 48;
            const long = i % 6 === 0;
            return (
              <line
                key={i}
                x1="0" y1={-92}
                x2="0" y2={long ? -84 : -88}
                stroke="currentColor"
                strokeWidth={long ? 0.9 : 0.5}
                opacity={long ? 0.85 : 0.4}
                transform={`rotate(${a})`}
              />
            );
          })}
        </g>

        {/* mid ring with cardinal marks */}
        <g className="ring-mid">
          <circle cx="0" cy="0" r="72" fill="none" stroke="currentColor" strokeWidth="0.5" opacity="0.4" />
          <circle cx="0" cy="0" r="66" fill="none" stroke="currentColor" strokeWidth="0.4" opacity="0.25" />
          {[0, 90, 180, 270].map((a) => (
            <g key={a} transform={`rotate(${a})`}>
              <polygon points="0,-72 -3,-64 3,-64" fill="currentColor" opacity="0.85" />
            </g>
          ))}
          {[45, 135, 225, 315].map((a) => (
            <g key={a} transform={`rotate(${a})`}>
              <circle cx="0" cy="-68" r="1.2" fill="currentColor" opacity="0.7" />
            </g>
          ))}
        </g>

        {/* inner ring */}
        <g className="ring-inner">
          <circle cx="0" cy="0" r="48" fill="none" stroke="currentColor" strokeWidth="0.4" opacity="0.5" />
          <circle cx="0" cy="0" r="44" fill="none" stroke="currentColor" strokeWidth="0.3" opacity="0.3" strokeDasharray="1 3" />
        </g>

        {/* pulsing core — scales of balance */}
        <g className="pulse">
          <circle cx="0" cy="0" r="36" fill="url(#sg-core)" />
          <g stroke="currentColor" fill="none" strokeWidth="1.1" strokeLinecap="round">
            <line x1="0" y1="-22" x2="0" y2="22" opacity="0.95" />
            <line x1="-16" y1="-8" x2="16" y2="-8" opacity="0.9" />
            <circle cx="-16" cy="-8" r="2.2" fill="currentColor" opacity="0.9" stroke="none" />
            <circle cx="16"  cy="-8" r="2.2" fill="currentColor" opacity="0.9" stroke="none" />
            <polygon points="0,22 -5,14 5,14" fill="currentColor" opacity="0.9" stroke="none" />
          </g>
          <circle cx="0" cy="-22" r="1.6" fill="currentColor" />
        </g>
      </svg>
    </div>
  );
}

window.Sigil = Sigil;
