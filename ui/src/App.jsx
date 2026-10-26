
import { useEffect, useRef, useState } from 'react';
import SpeedTest from '@cloudflare/speedtest';
import {
  Activity, ArrowDownToLine, ArrowUpFromLine, CheckCircle2,
  Gauge, Globe2, Laptop2, RefreshCw, Router, Shield,
  Signal, Wifi, Zap, Gamepad2,
} from 'lucide-react';
import StabilityPanel from './StabilityPanel.jsx';
import ActivityPanel from './ActivityPanel.jsx';
import DiagnosisPanel from './DiagnosisPanel.jsx';
import {
  FeedbackHub,
  FeedbackButton,
  notify,
  beginTask,
} from './feedback.jsx';

const MEASUREMENTS = [
  { type: 'latency', numPackets: 6 },
  { type: 'download', bytes: 100_000, count: 2, bypassMinDuration: true },
  { type: 'download', bytes: 1_000_000, count: 3, bypassMinDuration: true },
  { type: 'download', bytes: 4_000_000, count: 2, bypassMinDuration: true },
  { type: 'upload', bytes: 100_000, count: 2, bypassMinDuration: true },
  { type: 'upload', bytes: 1_000_000, count: 3, bypassMinDuration: true },
  { type: 'upload', bytes: 4_000_000, count: 2, bypassMinDuration: true },
];

const EMPTY = {
  status: 'unverified',
  headline: 'Checking your connection…',
  explanation: 'Gathering a quick network overview.',
  observation: '',
  next_step: '',
  interface: '—',
  gateway: '—',
  network: null,
  vpn: 'Not checked',
  proxy: 'Not checked',
  isp: 'Not checked',
  hotspot: 'Not determined',
  cgnat: 'Not checked',
};

function measured(results, key, divisor = 1) {
  try {
    const n = results?.[key]?.();
    return typeof n === 'number' && Number.isFinite(n) && n >= 0
      ? n / divisor
      : null;
  } catch {
    return null;
  }
}

function readings(results) {
  return {
    download_mbps: measured(
      results, 'getDownloadBandwidth', 1_000_000
    ),
    upload_mbps: measured(
      results, 'getUploadBandwidth', 1_000_000
    ),
    latency_ms: measured(results, 'getUnloadedLatency'),
    jitter_ms: measured(results, 'getUnloadedJitter'),
    tested_at: new Date().toISOString(),
  };
}

function speedText(n) {
  return typeof n === 'number' && Number.isFinite(n)
    ? n.toFixed(n >= 100 ? 0 : 1)
    : '—';
}

function msText(n) {
  return typeof n === 'number' && Number.isFinite(n)
    ? `${n.toFixed(0)} ms`
    : 'Not measured';
}

function SpeedDial({ label, value, direction, busy }) {
  const Icon = direction === 'download'
    ? ArrowDownToLine
    : ArrowUpFromLine;

  const max = value > 500 ? 1000 : value > 150 ? 500 : 150;
  const progress = typeof value === 'number'
    ? Math.min(100, 100 * value / max)
    : 0;

  return (
    <section
      className={`dial-card ${direction}`}
      aria-label={`${label} speed`}
    >
      <div className="dial-caption">
        <Icon size={18} /> {label}
      </div>

      <div className="dial-wrap">
        <svg
          className="dial"
          viewBox="0 0 220 220"
          aria-hidden="true"
        >
          <circle
            cx="110"
            cy="110"
            r="89"
            className="dial-track"
          />
          <circle
            cx="110"
            cy="110"
            r="89"
            className="dial-progress"
            pathLength="100"
            strokeDasharray={`${progress} 100`}
          />
        </svg>

        <div className="dial-reading">
          <strong>{speedText(value)}</strong>
          <span>Mbps</span>
        </div>
      </div>

      <p>
        {busy
          ? 'Measuring…'
          : value == null
            ? 'No speed measurement yet'
            : 'Latest completed sample'}
      </p>
    </section>
  );
}

function DataLine({ label, value, quiet }) {
  return (
    <div className="data-line">
      <span>{label}</span>
      <strong className={quiet ? 'unknown' : ''}>
        {value ?? 'Not checked'}
      </strong>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState('dashboard');
  const [overview, setOverview] = useState(EMPTY);
  const [checking, setChecking] = useState(true);
  const [speed, setSpeed] = useState(null);
  const [speedState, setSpeedState] = useState('idle');
  const [speedError, setSpeedError] = useState('');
  const [publicInfo, setPublicInfo] = useState(null);
  const [publicBusy, setPublicBusy] = useState(false);
  const [publicError, setPublicError] = useState('');
  const [wanIp, setWanIp] = useState('');

  const testerRef = useRef(null);
  const overviewBusyRef = useRef(false);
  const speedTimerRef = useRef(null);

  async function refreshOverview(silent = false) {
    if (overviewBusyRef.current) return;

    if (!window.pywebview?.api?.get_overview) {
      setChecking(false);
      if (!silent) {
        notify(
          'warning',
          'Connection check unavailable',
          'Open NetDoctor in its Windows window.'
        );
      }
      return;
    }

    overviewBusyRef.current = true;

    const finish = silent
      ? null
      : beginTask(
          'Checking basic connectivity…',
          'Testing current Windows network access.'
        );

    setChecking(true);

    try {
      const result = await window.pywebview.api.get_overview();
      setOverview(result);

      finish?.(
        result.status === 'unverified' ? 'warning' : 'success',
        'Connection check completed',
        result.headline
      );
    } catch {
      setOverview({
        ...EMPTY,
        headline: 'Connection check unavailable',
        explanation: 'Try checking again.',
      });

      finish?.(
        'error',
        'Connection check failed',
        'NetDoctor could not complete the request.'
      );
    } finally {
      overviewBusyRef.current = false;
      setChecking(false);
    }
  }

  function openTab(id, label) {
    setTab(id);

    notify(
      'info',
      `${label} opened`,
      'You can use the controls on this page.'
    );
  }

  useEffect(() => {
    let active = true;

    async function ready() {
      await refreshOverview(true);

      try {
        const old =
          await window.pywebview?.api?.load_previous_speed();

        if (active && old) {
          setSpeed(old);
        }
      } catch {
        // No earlier reading is normal.
      }
    }

    if (window.pywebview?.api) {
      ready();
    } else {
      window.addEventListener(
        'pywebviewready',
        ready,
        { once: true }
      );
    }

    return () => {
      active = false;
      window.removeEventListener('pywebviewready', ready);
    };
  }, []);

  function startSpeedTest() {
    if (testerRef.current || speedState === 'running') return;

    if (!window.confirm(
      'This test transfers up to about 22.4 MB plus overhead ' +
      '(11.2 MB download and 11.2 MB upload). Mobile data may be charged. ' +
      'Traffic goes to an external speed-test provider. Continue?'
    )) {
      notify(
        'info',
        'Speed test cancelled',
        'No speed-test data was requested.'
      );
      return;
    }

    const finish = beginTask(
      'Speed test running…',
      'Measuring download, upload and latency.'
    );

    setSpeedState('running');
    setSpeedError('');

    try {
      const tester = new SpeedTest({
        autoStart: false,
        measurements: MEASUREMENTS,
        measureDownloadLoadedLatency: false,
        measureUploadLoadedLatency: false,
      });

      testerRef.current = tester;

      tester.onResultsChange = () => {
        setSpeed(readings(tester.results));
      };

      tester.onError = () => {
        setSpeedError(
          'Some requests failed. Results may be incomplete.'
        );
      };

      tester.onFinish = async results => {
        if (testerRef.current !== tester) return;

        if (speedTimerRef.current) {
          window.clearTimeout(speedTimerRef.current);
        }

        speedTimerRef.current = null;

        const final = readings(results);
        setSpeed(final);

        const complete =
          final.download_mbps != null &&
          final.upload_mbps != null;

        setSpeedState(complete ? 'complete' : 'incomplete');

        if (complete) {
          finish(
            'success',
            'Speed test completed',
            `${final.download_mbps.toFixed(1)} Mbps down · ` +
            `${final.upload_mbps.toFixed(1)} Mbps up`
          );

          try {
            await window.pywebview?.api?.save_speed(final);
          } catch {
            setSpeedError(
              'Results were measured but could not be saved.'
            );

            notify(
              'warning',
              'Speed results not saved',
              'The measurements are still visible until you close this window.'
            );
          }
        } else {
          finish(
            'warning',
            'Speed test incomplete',
            'One or both speed measurements are unavailable.'
          );
        }

        testerRef.current = null;
      };

      speedTimerRef.current = window.setTimeout(() => {
        if (testerRef.current !== tester) return;

        try {
          if (typeof tester.pause === 'function') {
            tester.pause();
          }
        } catch {
          // Timeout already recorded.
        }

        testerRef.current = null;
        speedTimerRef.current = null;

        setSpeedState('incomplete');
        setSpeedError(
          'Speed test took too long. Partial readings are not saved.'
        );

        finish(
          'warning',
          'Speed test timed out',
          'The requested sample did not finish within 90 seconds.'
        );
      }, 90000);

      tester.play();
    } catch {
      if (speedTimerRef.current) {
        window.clearTimeout(speedTimerRef.current);
      }

      speedTimerRef.current = null;
      setSpeedState('incomplete');
      setSpeedError('Speed test could not start. Try again.');

      finish(
        'error',
        'Speed test could not start',
        'Check your connection and retry.'
      );

      testerRef.current = null;
    }
  }

  async function checkPublic() {
    if (publicBusy) return;

    if (!window.pywebview?.api?.check_public_connection) {
      setPublicError(
        'Open the Windows NetDoctor app for this check.'
      );

      notify(
        'error',
        'Public lookup unavailable',
        'The desktop connection is not ready.'
      );
      return;
    }

    if (!window.confirm(
      'NetDoctor will contact IP.SB once over HTTPS. The service sees your ' +
      'exit IP and returns its operator. Your optional router WAN address stays local. Continue?'
    )) {
      notify(
        'info',
        'Public lookup cancelled',
        'No public-IP request was made.'
      );
      return;
    }

    const finish = beginTask(
      'Checking public connection…',
      'Waiting for the external network lookup.'
    );

    setPublicBusy(true);
    setPublicError('');
    setPublicInfo(null);

    try {
      const response =
        await window.pywebview.api.check_public_connection(
          wanIp.trim()
        );

      if (response?.ok && response.report) {
        setPublicInfo(response.report);

        finish(
          'success',
          'Public lookup completed',
          'Exit network and NAT clues are shown below.'
        );
      } else {
        setPublicError(
          response?.error || 'Public connection lookup failed.'
        );

        finish(
          'warning',
          'Public lookup did not complete',
          response?.error || 'No usable result returned.'
        );
      }
    } catch {
      setPublicError(
        'Public connection lookup could not finish.'
      );

      finish(
        'error',
        'Public lookup failed',
        'Try again when your connection is available.'
      );
    } finally {
      setPublicBusy(false);
    }
  }

  const good = overview.status === 'reachable';
  const wifi = overview.network?.wifi;
  const vpn = overview.network?.vpn;
  const proxy = overview.network?.proxy;

  const wifiLabel = wifi?.signal_percent != null
    ? `${wifi.signal_percent}% · ${wifi.signal_label}`
    : wifi?.adapter_link_speed
      ? `Connected · ${wifi.adapter_link_speed} link`
      : wifi?.status || 'Not checked';

  const when = speed?.tested_at
    ? new Date(speed.tested_at).toLocaleString()
    : null;

  const age = speed?.tested_at
    ? Date.now() - new Date(speed.tested_at).getTime()
    : null;

  const speedOld =
    age != null &&
    (
      !Number.isFinite(age) ||
      age > 2 * 3600000 ||
      age < -300000
    );

  const navigation = [
    ['dashboard', 'Overview', Gauge],
    ['diagnosis', 'Diagnosis', Activity],
    ['activities', 'Activities', Gamepad2],
    ['stability', 'Stability', Signal],
    ['details', 'Network details', Laptop2],
  ];

  return (
    <div className="shell">
      <FeedbackHub />

      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Activity size={24} />
          </div>

          <span>
            Net<span className="brand-accent">Doctor</span>
          </span>
        </div>

        <div className="menu-label">
          WORKSPACE
        </div>

        {navigation.map(([id, label, Icon]) => (
          <button
            key={id}
            className={`nav ${tab === id ? 'selected' : ''}`}
            onClick={() => openTab(id, label)}
          >
            <Icon size={19} /> {label}
          </button>
        ))}

        <div className="sidebar-bottom">
          <span className="side-dot" /> Local Windows app
          <small>No account or subscription</small>
        </div>
      </aside>

      <main className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">
              NETWORK CONTROL CENTER
            </p>

            <h1>
              {({
                dashboard: 'Your connection at a glance',
                diagnosis: 'Network diagnosis',
                activities: 'Activity insights',
                stability: 'Stability & history',
                details: 'Connection details',
              })[tab]}
            </h1>
          </div>

          <div
            className={`connection-pill ${good ? 'online' : ''}`}
          >
            <span className="pulse" />

            {checking
              ? 'Checking'
              : good
                ? 'Basic access confirmed'
                : 'Needs checking'}
          </div>
        </header>

        <div key={tab} className="nd-page-enter">
          {tab === 'dashboard' && (
            <>
              <section className="speed-section">
                <div className="section-title">
                  <div>
                    <p className="eyebrow">
                      SPEED TEST ON DEMAND
                    </p>
                    <h2>Internet speed</h2>
                  </div>

                  <FeedbackButton
                    className="primary"
                    onClick={startSpeedTest}
                    busy={speedState === 'running'}
                  >
                    <Zap size={17} />

                    {speedState === 'running'
                      ? 'Testing connection…'
                      : speed
                        ? 'Test again'
                        : 'Run speed test'}
                  </FeedbackButton>
                </div>

                <div className="speed-grid">
                  <SpeedDial
                    label="DOWNLOAD"
                    direction="download"
                    value={speed?.download_mbps ?? null}
                    busy={speedState === 'running'}
                  />

                  <SpeedDial
                    label="UPLOAD"
                    direction="upload"
                    value={speed?.upload_mbps ?? null}
                    busy={speedState === 'running'}
                  />
                </div>

                <div className="speed-footer">
                  <span>
                    {speedState === 'running'
                      ? 'Measuring download, upload and latency…'
                      : when
                        ? `Last measured: ${when}${
                            speedOld ? ' · Older reading' : ''
                          }`
                        : 'Run the test to measure current speed.'}
                  </span>

                  <span className="muted">
                    Manual test · About 23 MB plus overhead
                  </span>
                </div>

                {(speedError || speedState === 'incomplete') && (
                  <p className="inline-warning">
                    {speedError ||
                      'The test ended with incomplete measurements.'}
                  </p>
                )}
              </section>

              <section className="metric-row">
                <article className="mini-metric">
                  <Activity size={19} />
                  <span>LATENCY</span>
                  <strong>{msText(speed?.latency_ms)}</strong>
                </article>

                <article className="mini-metric">
                  <Signal size={19} />
                  <span>JITTER</span>
                  <strong>{msText(speed?.jitter_ms)}</strong>
                </article>

                <article className="mini-metric">
                  <Wifi size={19} />
                  <span>WI-FI</span>
                  <strong>{wifiLabel}</strong>
                </article>
              </section>

              <section className="lower-grid">
                <article className="panel diagnosis-panel">
                  <div className="panel-heading">
                    <h3>
                      <Shield size={19} /> Connection health
                    </h3>

                    <FeedbackButton
                      className="text-link"
                      onClick={() => refreshOverview(false)}
                      busy={checking}
                    >
                      <RefreshCw size={15} /> Recheck
                    </FeedbackButton>
                  </div>

                  <div className="health-title">
                    <CheckCircle2
                      size={24}
                      className={good ? 'good' : 'subtle'}
                    />

                    <strong>{overview.headline}</strong>
                  </div>

                  <p>{overview.explanation}</p>

                  {overview.network?.observation && (
                    <p className="inline-warning">
                      {overview.network.observation}
                    </p>
                  )}

                  <button
                    className="detail-link"
                    onClick={() => openTab('diagnosis', 'Diagnosis')}
                  >
                    Investigate possible causes →
                  </button>

                  <div style={{ marginTop: 16 }}>
                    <button
                      className="detail-link"
                      onClick={() => openTab('activities', 'Activities')}
                    >
                      Gaming, streaming and video-call insights →
                    </button>
                  </div>
                </article>

                <article className="panel">
                  <div className="panel-heading">
                    <h3>
                      <Router size={19} /> Network snapshot
                    </h3>
                  </div>

                  <DataLine
                    label="Connected via"
                    value={overview.interface}
                  />

                  <DataLine
                    label="Wi-Fi"
                    value={wifiLabel}
                  />

                  <DataLine
                    label="VPN route"
                    value={vpn?.status ?? overview.vpn}
                    quiet
                  />

                  <DataLine
                    label="Exit IP network"
                    value={
                      publicInfo?.exit_network ?? 'Not checked'
                    }
                    quiet={!publicInfo}
                  />

                  <DataLine
                    label="CGNAT"
                    value={
                      publicInfo?.nat_status ?? 'Not checked'
                    }
                    quiet
                  />

                  <button
                    className="detail-link"
                    onClick={() => openTab('details', 'Network details')}
                  >
                    Check public IP and connection details →
                  </button>
                </article>
              </section>
            </>
          )}

          {tab === 'diagnosis' && (
            <DiagnosisPanel
              overview={overview}
              reading={speedState === 'running' ? null : speed}
              onRecheck={() => refreshOverview(false)}
              checking={checking}
            />
          )}

          {tab === 'activities' && (
            <ActivityPanel
              reading={speedState === 'running' ? null : speed}
            />
          )}

          {tab === 'stability' && <StabilityPanel />}

          {tab === 'details' && (
            <section className="panel details-panel">
              <p className="eyebrow">
                ADVANCED INFORMATION
              </p>
              <h2>Your network</h2>

              <DataLine
                label="Internet-facing adapter"
                value={overview.interface}
              />

              <DataLine
                label="Gateway"
                value={overview.gateway}
              />

              <DataLine
                label="Wi-Fi adapter"
                value={
                  wifi?.adapter_description ??
                  wifi?.adapter_name ??
                  'Not available'
                }
              />

              <DataLine
                label="Wi-Fi link speed"
                value={
                  wifi?.adapter_link_speed ?? 'Not available'
                }
              />

              <DataLine
                label="Wi-Fi signal"
                value={
                  wifi?.signal_percent != null
                    ? `${wifi.signal_percent}%`
                    : 'Restricted or unavailable'
                }
              />

              <DataLine
                label="Wi-Fi network"
                value={wifi?.ssid ?? 'Unavailable'}
              />

              <p className="disclaimer">
                {wifi?.detail ??
                  'Wi-Fi details have not been collected.'}
              </p>

              <DataLine
                label="VPN routing"
                value={vpn?.status ?? overview.vpn}
              />

              <p className="disclaimer">
                {vpn?.detail ?? 'Not checked.'}
              </p>

              <DataLine
                label="Proxy settings"
                value={proxy?.status ?? overview.proxy}
              />

              <p className="disclaimer">
                {proxy?.detail ?? 'Not checked.'}
              </p>

              <div className="diagnosis-block">
                <strong>Public IP and provider</strong>

                <p>
                  Optional: contact IP.SB to check the operator
                  of your exit IP. VPNs and proxies may change
                  this result.
                </p>

                <label
                  htmlFor="router-wan"
                  style={{
                    display: 'block',
                    marginTop: 12,
                    fontSize: 13,
                  }}
                >
                  Router WAN IPv4 (optional, from your router settings)
                </label>

                <input
                  id="router-wan"
                  type="text"
                  value={wanIp}
                  maxLength={45}
                  onChange={event => setWanIp(event.target.value)}
                  placeholder="e.g. 100.64.12.34"
                  style={{
                    margin: '8px 0 12px',
                    width: '100%',
                    maxWidth: 330,
                    padding: 11,
                    borderRadius: 8,
                    background: '#0b1528',
                    color: '#eef4ff',
                    border: '1px solid #37506e',
                  }}
                />

                <div>
                  <FeedbackButton
                    className="primary"
                    onClick={checkPublic}
                    busy={publicBusy}
                  >
                    <Globe2 size={17} />
                    {publicBusy
                      ? 'Checking…'
                      : 'Check public connection'}
                  </FeedbackButton>
                </div>

                {publicError && (
                  <p
                    className="inline-warning"
                    role="alert"
                  >
                    {publicError}
                  </p>
                )}

                {publicInfo && (
                  <div style={{ marginTop: 13 }}>
                    <DataLine
                      label="Observed public IP"
                      value={publicInfo.public_ip}
                    />

                    <DataLine
                      label="IP version"
                      value={publicInfo.ip_family}
                    />

                    <DataLine
                      label="Exit IP network"
                      value={
                        publicInfo.exit_network ?? 'Unknown'
                      }
                    />

                    <DataLine
                      label="Network ASN"
                      value={
                        publicInfo.asn != null
                          ? `AS${publicInfo.asn}`
                          : 'Unknown'
                      }
                    />

                    <DataLine
                      label="Local IPv4"
                      value={
                        publicInfo.local_ipv4 ?? 'Unknown'
                      }
                    />

                    <DataLine
                      label="CGNAT / NAT clues"
                      value={publicInfo.nat_status}
                    />

                    <p>{publicInfo.nat_explanation}</p>

                    <p className="disclaimer">
                      {publicInfo.provider_explanation}
                    </p>
                  </div>
                )}
              </div>

              <DataLine
                label="Hotspot identity"
                value={overview.hotspot}
                quiet
              />

              <p className="disclaimer">
                No hotspot identity is inferred from Wi-Fi alone.
                No router login, port scan or Windows location
                permission is required.
              </p>
            </section>
          )}
        </div>

        <footer>
          <Globe2 size={14} />
          Read-only diagnostics
          <span>·</span>
          No automatic speed test or public IP lookup
          <span>·</span>
          Results stored locally
        </footer>
      </main>
    </div>
  );
}
