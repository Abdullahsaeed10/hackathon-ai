// Router — History API with hash fallback.
function useRoute() {
  const getPath = () => {
    // Prefer pathname (History API), fall back to hash
    const p = window.location.pathname;
    if (p && p !== '/') return p;
    const h = window.location.hash || '#/';
    return h.startsWith('#') ? h.slice(1) : h;
  };
  const [route, setRoute] = React.useState(getPath());
  React.useEffect(() => {
    const onPop = () => setRoute(getPath());
    window.addEventListener('popstate', onPop);
    window.addEventListener('hashchange', onPop);
    return () => { window.removeEventListener('popstate', onPop); window.removeEventListener('hashchange', onPop); };
  }, []);
  return route;
}

window.nav = (path) => {
  try {
    window.history.pushState({}, '', path);
    window.dispatchEvent(new PopStateEvent('popstate'));
  } catch (e) {
    window.location.hash = '#' + path;
  }
  window.scrollTo({ top: 0, behavior: 'auto' });
};

// ── Theme ────────────────────────────────────────────────────────────────────

const THEME_KEY = 'verdict-theme';
function applyTheme(t) { document.documentElement.setAttribute('data-theme', t); }
function useTheme() {
  const [theme, setTheme] = React.useState(() => {
    try { const s = localStorage.getItem(THEME_KEY); if (s === 'dark' || s === 'light') return s; } catch (e) {}
    return 'dark';
  });
  React.useEffect(() => {
    applyTheme(theme);
    try { localStorage.setItem(THEME_KEY, theme); } catch (e) {}
  }, [theme]);
  return [theme, setTheme];
}

function ThemeToggle({ theme, setTheme }) {
  const isDark = theme === 'dark';
  return (
    <button
      className="theme-toggle"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      aria-label={`switch to ${isDark ? 'light' : 'dark'} mode`}
      title={`The court is in ${isDark ? 'night' : 'day'} session. Click to switch.`}
    >
      <span className={`seg ${isDark ? 'active' : ''}`}><span className="glyph">☾</span>NIGHT</span>
      <span className="sep" />
      <span className={`seg ${!isDark ? 'active' : ''}`}>DAY<span className="glyph">☀</span></span>
    </button>
  );
}

// ── App ──────────────────────────────────────────────────────────────────────

function App() {
  const route = useRoute();
  const [theme, setTheme] = useTheme();

  let view;
  const r = route || '/';
  if (r === '/' || r === '') view = <Landing />;
  else if (r === '/scout') view = <Scout />;
  else if (r === '/judgment' || r === '/doctor') view = <Judgment />;
  else if (r.startsWith('/v/')) view = <Permalink id={r.slice(3)} />;
  else view = <Landing />;

  return (
    <React.Fragment>
      {view}
      <ThemeToggle theme={theme} setTheme={setTheme} />
    </React.Fragment>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
