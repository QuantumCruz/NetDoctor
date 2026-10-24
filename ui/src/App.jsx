
import { useEffect, useRef, useState } from 'react';
import SpeedTest from '@cloudflare/speedtest';
import {
  Activity, ArrowDownToLine, ArrowUpFromLine, CheckCircle2,
  Gauge as GaugeIcon, Globe2, Laptop2, RefreshCw, Router,
  Shield, Signal, Wifi, Zap,
} from 'lucide-react';

// Explicitly bounded measurements, rather than the provider's large defaults.
const MEASUREMENTS = [
  { type: 'latency', numPackets: 6 },
  { type: 'download', bytes: 100_000, count: 2, bypassMinDuration: true },
  { type: 'download', bytes: 1_000_000, count: 3, bypassMinDuration: true },
  { type: 'download', bytes: 4_000_000, count: 2, bypassMinDuration: true },
  { type: 'upload', bytes: 100_000, count: 2, bypassMinDuration: true },
  { type: 'upload', bytes: 1_000_000, count: 3, bypassMinDuration: true },
  { type: 'upload', bytes: 4_000_000, count: 2, bypassMinDuration: true },
];

function optionalMeasurement(results, name, scale = 1) {
  try {
    const result = results?.[name]?.();
    return typeof result === 'number' &&
      Number.isFinite(result) && result >= 0
      ? result / scale : null;
  } catch {
    return null;
  }
}

function extractMeasurements(results) {
  return {
    download_mbps: optionalMeasurement(
      results, 'getDownloadBandwidth', 1_000_000
    ),
    upload_mbps: optionalMeasurement(
      results, 'getUploadBandwidth', 1_000_000
    ),
    latency_ms: optionalMeasurement(results, 'getUnloadedLatency'),
    jitter_ms: optionalMeasurement(results, 'getUnloadedJitter'),
    tested_at: new Date().toISOString(),
  };
}

function formatSpeed(value) {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toFixed(value >= 100 ? 0 : 1) : '—';
}

function formatLatency(value) {
  return typeof value === 'number' && Number.isFinite(value)
    ? `${value.toFixed(0)} ms` : 'Not measured';
}

function SpeedDial({ label, value, direction, busy = false }) {
  const maximum = value > 500 ? 1000 : value > 150 ? 500 : 150;
  const progress = typeof value === 'number'
    ? Math.min(100, 100 * value / maximum) : 0;
  const Icon = direction === 'download'
    ? ArrowDownToLine : ArrowUpFromLine;

  return (
    <section className={`dial-card ${direction}`}
      aria-label={`${label} speed`}>
      <div className="dial-caption">
        <Icon size={18} /> {label}
      </div>
      <div className="dial-wrap">
        <svg className="dial" viewBox="0 0 220 220"
          role="presentation" aria-hidden="true">
          <circle cx="110" cy="110" r="89" className="dial-track" />
          <circle cx="110" cy="110" r="89"
            className="dial-progress" pathLength="100"
            strokeDasharray={`${progress} 100`} />
        </svg>
        <div className="dial-reading">
          <strong>{formatSpeed(value)}</strong>
          <span>Mbps</span>
        </div>
      </div>
      <p>{busy ? 'Measuring…' : value === null
        ? 'No speed measurement yet'
        : 'Latest completed sample'}</p>
    </section>
  );
}

const defaultOverview = {
  status: 'unverified',
  headline: 'Checking your connection…',
  explanation: 'Gathering a quick network overview.',
  observation: '',
  next_step: '',
  interface: '—',
  gateway: '—',
  vpn: 'Not checked',
  isp: 'Not checked',
  hotspot: 'Not checked',
  cgnat: 'Not checked',
};

export default function App() {
  const [tab, setTab] = useState('dashboard');
  const [overview, setOverview] = useState(defaultOverview);
  const [checking, setChecking] = useState(true);
  const [speed, setSpeed] = useState(null);
  const [speedState, setSpeedState] = useState('idle');
  const [speedError, setSpeedError] = useState('');
  const testerRef = useRef(null);

  async function refreshOverview() {
    if (!window.pywebview?.api) {
      setChecking(false);
      return;
    }

    setChecking(true);
    try {
      const result = await window.pywebview.api.get_overview();
      setOverview(result);
    } catch {
      setOverview({
        ...defaultOverview,
        headline: 'Could not check the network',
        explanation: 'Try checking again.',
      });
    } finally {
      setChecking(false);
    }
  }

  useEffect(() => {
    const ready = async () => {
      await refreshOverview();
      try {
        const previous =
          await window.pywebview.api.load_previous_speed();
        if (previous) setSpeed(previous);
      } catch {
        // Previous readings are optional.
      }
    };

    if (window.pywebview?.api) ready();
    else window.addEventListener('pywebviewready', ready, { once: true });

    return () => window.removeEventListener('pywebviewready', ready);
  }, []);

  function startSpeedTest() {
    if (speedState === 'running') return;

    const consent = window.confirm(
      'NetDoctor will transfer up to about 22.4 MB of test data ' +
      '(11.2 MB down and 11.2 MB up), plus small request overhead. ' +
      'This may use your mobile data allowance. Test data goes to an ' +
      'external speed-test provider. Continue?'
    );
    if (!consent) return;

    setSpeedError('');
    setSpeedState('running');
    setSpeed(null);

    try {
      const tester = new SpeedTest({
        autoStart: false,
        measurements: MEASUREMENTS,
        measureDownloadLoadedLatency: false,
        measureUploadLoadedLatency: false,
      });

      testerRef.current = tester;

      tester.onResultsChange = () => {
        const current = extractMeasurements(tester.results);
        setSpeed(current);
      };

      tester.onError = () => {
        setSpeedError(
          'Some measurement requests failed. Results may be incomplete.'
        );
      };

      tester.onFinish = async results => {
        const final = extractMeasurements(results);
        setSpeed(final);
        setSpeedState(
          final.download_mbps !== null && final.upload_mbps !== null
            ? 'complete' : 'incomplete'
        );

        if (
          final.download_mbps !== null &&
          final.upload_mbps !== null
        ) {
          try {
            await window.pywebview?.api?.save_speed(final);
          } catch {
            setSpeedError(
              'Results were measured but could not be saved.'
            );
          }
        }

        testerRef.current = null;
      };

      tester.play();
    } catch {
      setSpeedState('incomplete');
      setSpeedError(
        'The speed test could not start. ' +
        'Check your connection and try again.'
      );
      testerRef.current = null;
    }
  }

  const statusGood = overview.status === 'reachable';
  const completedAt = speed?.tested_at
    ? new Date(speed.tested_at).toLocaleString()
    : null;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Activity size={24} />
          </div>
          <span>Net<span className="brand-accent">Doctor</span></span>
        </div>

        <div className="menu-label">WORKSPACE</div>

        <button className={`nav ${tab === 'dashboard' ? 'selected' : ''}`}
          onClick={() => setTab('dashboard')}>
          <GaugeIcon size={19} /> Overview
        </button>

        <button className={`nav ${tab === 'diagnosis' ? 'selected' : ''}`}
          onClick={() => setTab('diagnosis')}>
          <Activity size={19} /> Diagnosis
        </button>

        <button className={`nav ${tab === 'details' ? 'selected' : ''}`}
          onClick={() => setTab('details')}>
          <Laptop2 size={19} /> Network details
        </button>

        <div className="sidebar-bottom">
          <span className="side-dot" /> Local Windows app
          <small>No account or subscription</small>
        </div>
      </aside>

      <main className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">NETWORK CONTROL CENTER</p>
            <h1>{tab === 'dashboard'
              ? 'Your connection at a glance'
              : tab === 'diagnosis'
                ? 'Network diagnosis'
                : 'Connection details'}</h1>
          </div>

          <div className={`connection-pill ${statusGood ? 'online' : ''}`}>
            <span className="pulse" />
            {checking ? 'Checking'
              : statusGood
                ? 'Basic access confirmed'
                : 'Needs checking'}
          </div>
        </header>

        {tab === 'dashboard' && (
          <>
            <section className="speed-section">
              <div className="section-title">
                <div>
                  <p className="eyebrow">SPEED TEST ON DEMAND</p>
                  <h2>Internet speed</h2>
                </div>

                <button className="primary"
                  disabled={speedState === 'running'}
                  onClick={startSpeedTest}>
                  <Zap size={17} />
                  {speedState === 'running'
                    ? 'Testing connection…'
                    : speed
                      ? 'Test again'
                      : 'Run speed test'}
                </button>
              </div>

              <div className="speed-grid">
                <SpeedDial label="DOWNLOAD"
                  value={speed?.download_mbps ?? null}
                  direction="download"
                  busy={speedState === 'running'} />
                <SpeedDial label="UPLOAD"
                  value={speed?.upload_mbps ?? null}
                  direction="upload"
                  busy={speedState === 'running'} />
              </div>

              <div className="speed-footer">
                <span>
                  {speedState === 'running'
                    ? 'Measuring download, upload and latency…'
                    : completedAt
                      ? `Last measured: ${completedAt}`
                      : 'Run the test to measure your current speed.'}
                </span>
                <span className="muted">
                  Manual test · About 23 MB plus overhead
                </span>
              </div>

              {(speedError || speedState === 'incomplete') && (
                <p className="inline-warning">
                  {speedError ||
                    'The test ended without enough valid speed data.'}
                </p>
              )}
            </section>

            <section className="metric-row">
              <article className="mini-metric">
                <Activity size={19} />
                <span>LATENCY</span>
                <strong>{formatLatency(speed?.latency_ms)}</strong>
              </article>

              <article className="mini-metric">
                <Signal size={19} />
                <span>JITTER</span>
                <strong>{formatLatency(speed?.jitter_ms)}</strong>
              </article>

              <article className="mini-metric">
                <Wifi size={19} />
                <span>CONNECTION</span>
                <strong>{overview.interface}</strong>
              </article>
            </section>

            <section className="lower-grid">
              <article className="panel diagnosis-panel">
                <div className="panel-heading">
                  <h3><Shield size={19} /> Connection health</h3>
                  <button className="text-link"
                    onClick={refreshOverview}
                    disabled={checking}>
                    <RefreshCw size={15} /> Recheck
                  </button>
                </div>

                <div className="health-title">
                  <CheckCircle2
                    className={statusGood ? 'good' : 'subtle'}
                    size={24} />
                  <strong>{overview.headline}</strong>
                </div>

                <p>{overview.explanation}</p>

                <button className="detail-link"
                  onClick={() => setTab('diagnosis')}>
                  See what we found →
                </button>
              </article>

              <article className="panel">
                <div className="panel-heading">
                  <h3><Router size={19} /> Network snapshot</h3>
                </div>

                <div className="data-line">
                  <span>Connected via</span>
                  <strong>{overview.interface}</strong>
                </div>

                <div className="data-line">
                  <span>VPN</span>
                  <strong className="unknown">{overview.vpn}</strong>
                </div>

                <div className="data-line">
                  <span>Internet provider</span>
                  <strong className="unknown">{overview.isp}</strong>
                </div>

                <div className="data-line">
                  <span>CGNAT / hotspot</span>
                  <strong className="unknown">Not checked</strong>
                </div>

                <button className="detail-link"
                  onClick={() => setTab('details')}>
                  View connection details →
                </button>
              </article>
            </section>
          </>
        )}

        {tab === 'diagnosis' && (
          <section className="panel details-panel">
            <p className="eyebrow">WHAT WE FOUND</p>
            <h2>{overview.headline}</h2>
            <p>{overview.explanation}</p>

            <div className="diagnosis-block">
              <strong>Worth knowing</strong>
              <p>
                {overview.observation ||
                  'No additional observation yet.'}
              </p>
            </div>

            <div className="diagnosis-block action">
              <strong>Recommended next step</strong>
              <p>{overview.next_step}</p>
            </div>

            <button className="primary"
              onClick={refreshOverview}
              disabled={checking}>
              <RefreshCw size={17} />
              {checking
                ? 'Checking…'
                : 'Run a new quick check'}
            </button>

            <p className="disclaimer">
              This is an evidence-based snapshot,
              not a complete internet quality rating.
            </p>
          </section>
        )}

        {tab === 'details' && (
          <section className="panel details-panel">
            <p className="eyebrow">ADVANCED INFORMATION</p>
            <h2>Your network</h2>

            <div className="data-line">
              <span>Internet-facing adapter</span>
              <strong>{overview.interface}</strong>
            </div>

            <div className="data-line">
              <span>Default gateway</span>
              <strong>{overview.gateway}</strong>
            </div>

            <div className="data-line">
              <span>VPN / proxy detection</span>
              <strong>Not implemented yet</strong>
            </div>

            <div className="data-line">
              <span>Hotspot detection</span>
              <strong>Not implemented yet</strong>
            </div>

            <div className="data-line">
              <span>ISP and CGNAT analysis</span>
              <strong>Not implemented yet</strong>
            </div>

            <div className="data-line">
              <span>Speed test provider</span>
              <strong>Cloudflare</strong>
            </div>

            <p className="disclaimer">
              Speed figures are short samples to an external
              test service, not guaranteed plan speeds.
              VPN, hotspot and NAT fields will only show
              results after real detection is built.
            </p>
          </section>
        )}

        <footer>
          <Globe2 size={14} />
          Read-only diagnostics
          <span>·</span>
          No automatic speed-test data use
          <span>·</span>
          Results stored on this device
        </footer>
      </main>
    </div>
  );
}
