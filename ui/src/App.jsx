
import { useEffect, useRef, useState } from 'react';
import SpeedTest from '@cloudflare/speedtest';
import {
  Activity, ArrowDownToLine, ArrowUpFromLine, CheckCircle2,
  Gauge, Globe2, Laptop2, RefreshCw, Router, Shield, Signal, Wifi, Zap,
} from 'lucide-react';

// Explicitly bounded; never run automatically. One click requires consent.
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
  status: 'unverified', headline: 'Checking your connection…',
  explanation: 'Gathering a quick network overview.', observation: '',
  next_step: '', interface: '—', gateway: '—', network: null,
  vpn: 'Not checked', proxy: 'Not checked', isp: 'Not checked',
  hotspot: 'Not determined', cgnat: 'Not checked',
};

function valueOf(results, getter, divisor = 1) {
  try {
    const value = results?.[getter]?.();
    return typeof value === 'number' && Number.isFinite(value) && value >= 0
      ? value / divisor : null;
  } catch { return null; }
}

function readings(results) {
  return {
    download_mbps: valueOf(results, 'getDownloadBandwidth', 1_000_000),
    upload_mbps: valueOf(results, 'getUploadBandwidth', 1_000_000),
    latency_ms: valueOf(results, 'getUnloadedLatency'),
    jitter_ms: valueOf(results, 'getUnloadedJitter'),
    tested_at: new Date().toISOString(),
  };
}

function speedNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toFixed(value >= 100 ? 0 : 1) : '—';
}

function millis(value) {
  return typeof value === 'number' && Number.isFinite(value)
    ? `${value.toFixed(0)} ms` : 'Not measured';
}

function SpeedDial({ label, value, direction, busy }) {
  const Icon = direction === 'download' ? ArrowDownToLine : ArrowUpFromLine;
  const maximum = value > 500 ? 1000 : value > 150 ? 500 : 150;
  const pct = typeof value === 'number' ? Math.min(100, value / maximum * 100) : 0;
  return (
    <section className={`dial-card ${direction}`} aria-label={`${label} speed`}>
      <div className="dial-caption"><Icon size={18} /> {label}</div>
      <div className="dial-wrap">
        <svg className="dial" viewBox="0 0 220 220" aria-hidden="true">
          <circle cx="110" cy="110" r="89" className="dial-track" />
          <circle cx="110" cy="110" r="89" className="dial-progress"
            pathLength="100" strokeDasharray={`${pct} 100`} />
        </svg>
        <div className="dial-reading"><strong>{speedNumber(value)}</strong><span>Mbps</span></div>
      </div>
      <p>{busy ? 'Measuring…' : value == null
        ? 'No speed measurement yet' : 'Latest completed sample'}</p>
    </section>
  );
}

function DataLine({ label, value, quiet }) {
  return (
    <div className="data-line">
      <span>{label}</span>
      <strong className={quiet ? 'unknown' : ''}>{value ?? 'Not checked'}</strong>
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

  async function refreshOverview() {
    if (!window.pywebview?.api) { setChecking(false); return; }
    setChecking(true);
    try {
      setOverview(await window.pywebview.api.get_overview());
    } catch {
      setOverview({ ...EMPTY, headline: 'Connection check unavailable',
        explanation: 'Try checking again.' });
    } finally { setChecking(false); }
  }

  useEffect(() => {
    let active = true;
    const ready = async () => {
      await refreshOverview();
      try {
        const previous = await window.pywebview?.api?.load_previous_speed();
        if (active && previous) setSpeed(previous);
      } catch { /* No previous reading is normal. */ }
    };
    if (window.pywebview?.api) ready();
    else window.addEventListener('pywebviewready', ready, { once: true });
    return () => { active = false; window.removeEventListener('pywebviewready', ready); };
  }, []);

  function startSpeedTest() {
    if (speedState === 'running') return;
    if (!window.confirm('This test transfers up to about 22.4 MB plus overhead '
      + '(11.2 MB download and 11.2 MB upload). Mobile data may be charged. '
      + 'Traffic goes to an external speed-test provider. Continue?')) return;
    setSpeedState('running');
    setSpeedError('');
    try {
      const tester = new SpeedTest({
        autoStart: false, measurements: MEASUREMENTS,
        measureDownloadLoadedLatency: false,
        measureUploadLoadedLatency: false,
      });
      testerRef.current = tester;
      tester.onResultsChange = () => setSpeed(readings(tester.results));
      tester.onError = () => setSpeedError('Some measurement requests failed. Results may be incomplete.');
      tester.onFinish = async results => {
        const final = readings(results);
        setSpeed(final);
        const complete = final.download_mbps != null && final.upload_mbps != null;
        setSpeedState(complete ? 'complete' : 'incomplete');
        if (complete) {
          try { await window.pywebview?.api?.save_speed(final); }
          catch { setSpeedError('Results were measured but could not be saved.'); }
        }
        testerRef.current = null;
      };
      tester.play();
    } catch {
      setSpeedState('incomplete');
      setSpeedError('Speed test could not start. Try again.');
      testerRef.current = null;
    }
  }

  async function checkPublic() {
    if (publicBusy || !window.pywebview?.api?.check_public_connection) {
      setPublicError('Open NetDoctor in its Windows app to use this check.');
      return;
    }
    if (!window.confirm('NetDoctor will contact IP.SB once over HTTPS. '
      + 'The service sees your current exit IP address and returns its '
      + 'network operator. The optional router WAN address stays local. Continue?')) return;
    setPublicBusy(true);
    setPublicError('');
    setPublicInfo(null);
    try {
      const result = await window.pywebview.api.check_public_connection(wanIp.trim());
      if (result?.ok && result.report) setPublicInfo(result.report);
      else setPublicError(result?.error || 'Public connection lookup failed.');
    } catch {
      setPublicError('Public connection lookup could not finish.');
    } finally { setPublicBusy(false); }
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
  const when = speed?.tested_at ? new Date(speed.tested_at).toLocaleString() : null;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-icon"><Activity size={24}/></div>
          <span>Net<span className="brand-accent">Doctor</span></span></div>
        <div className="menu-label">WORKSPACE</div>
        <button className={`nav ${tab === 'dashboard' ? 'selected' : ''}`}
          onClick={() => setTab('dashboard')}><Gauge size={19}/> Overview</button>
        <button className={`nav ${tab === 'diagnosis' ? 'selected' : ''}`}
          onClick={() => setTab('diagnosis')}><Activity size={19}/> Diagnosis</button>
        <button className={`nav ${tab === 'details' ? 'selected' : ''}`}
          onClick={() => setTab('details')}><Laptop2 size={19}/> Network details</button>
        <div className="sidebar-bottom"><span className="side-dot"/> Local Windows app
          <small>No account or subscription</small></div>
      </aside>

      <main className="content">
        <header className="topbar">
          <div><p className="eyebrow">NETWORK CONTROL CENTER</p>
            <h1>{tab === 'dashboard' ? 'Your connection at a glance'
              : tab === 'diagnosis' ? 'Network diagnosis' : 'Connection details'}</h1></div>
          <div className={`connection-pill ${good ? 'online' : ''}`}>
            <span className="pulse"/>{checking ? 'Checking' : good
              ? 'Basic access confirmed' : 'Needs checking'}</div>
        </header>

        {tab === 'dashboard' && <>
          <section className="speed-section">
            <div className="section-title"><div>
              <p className="eyebrow">SPEED TEST ON DEMAND</p><h2>Internet speed</h2>
            </div><button className="primary" disabled={speedState === 'running'}
              onClick={startSpeedTest}><Zap size={17}/>
                {speedState === 'running' ? 'Testing connection…' : speed ? 'Test again' : 'Run speed test'}
            </button></div>
            <div className="speed-grid">
              <SpeedDial label="DOWNLOAD" value={speed?.download_mbps ?? null}
                direction="download" busy={speedState === 'running'} />
              <SpeedDial label="UPLOAD" value={speed?.upload_mbps ?? null}
                direction="upload" busy={speedState === 'running'} />
            </div>
            <div className="speed-footer"><span>{speedState === 'running'
              ? 'Measuring download, upload and latency…' : when
                ? `Last measured: ${when}` : 'Run the test to measure current speed.'}</span>
              <span className="muted">Manual test · About 23 MB plus overhead</span></div>
            {(speedError || speedState === 'incomplete') &&
              <p className="inline-warning">{speedError || 'The test ended with incomplete measurements.'}</p>}
          </section>

          <section className="metric-row">
            <article className="mini-metric"><Activity size={19}/><span>LATENCY</span>
              <strong>{millis(speed?.latency_ms)}</strong></article>
            <article className="mini-metric"><Signal size={19}/><span>JITTER</span>
              <strong>{millis(speed?.jitter_ms)}</strong></article>
            <article className="mini-metric"><Wifi size={19}/><span>WI-FI</span>
              <strong>{wifiLabel}</strong></article>
          </section>

          <section className="lower-grid">
            <article className="panel diagnosis-panel">
              <div className="panel-heading"><h3><Shield size={19}/> Connection health</h3>
                <button className="text-link" onClick={refreshOverview}
                  disabled={checking}><RefreshCw size={15}/> Recheck</button></div>
              <div className="health-title"><CheckCircle2 size={24}
                className={good ? 'good' : 'subtle'}/><strong>{overview.headline}</strong></div>
              <p>{overview.explanation}</p>
              {overview.network?.observation && <p className="inline-warning">{overview.network.observation}</p>}
              <button className="detail-link" onClick={() => setTab('diagnosis')}>See what we found →</button>
            </article>
            <article className="panel">
              <div className="panel-heading"><h3><Router size={19}/> Network snapshot</h3></div>
              <DataLine label="Connected via" value={overview.interface}/>
              <DataLine label="Wi-Fi" value={wifiLabel}/>
              <DataLine label="VPN route" value={vpn?.status ?? overview.vpn} quiet/>
              <DataLine label="Exit IP network" value={publicInfo?.exit_network ?? 'Not checked'} quiet={!publicInfo}/>
              <DataLine label="CGNAT" value={publicInfo?.nat_status ?? 'Not checked'} quiet/>
              <button className="detail-link" onClick={() => setTab('details')}>
                Check public IP and connection details →</button>
            </article>
          </section>
        </>}

        {tab === 'diagnosis' && <section className="panel details-panel">
          <p className="eyebrow">WHAT WE FOUND</p><h2>{overview.headline}</h2>
          <p>{overview.explanation}</p>
          <div className="diagnosis-block"><strong>Worth knowing</strong>
            <p>{overview.observation || 'No additional observation yet.'}</p></div>
          {overview.network?.observation && <div className="diagnosis-block">
            <strong>Network configuration</strong><p>{overview.network.observation}</p></div>}
          <div className="diagnosis-block action"><strong>Recommended next step</strong>
            <p>{overview.next_step}</p></div>
          <button className="primary" onClick={refreshOverview} disabled={checking}>
            <RefreshCw size={17}/>{checking ? 'Checking…' : 'Run a new quick check'}</button>
          <p className="disclaimer">A short diagnostic snapshot is not a guarantee of speed or stability.</p>
        </section>}

        {tab === 'details' && <section className="panel details-panel">
          <p className="eyebrow">ADVANCED INFORMATION</p><h2>Your network</h2>
          <DataLine label="Internet-facing adapter" value={overview.interface}/>
          <DataLine label="Gateway" value={overview.gateway}/>
          <DataLine label="Wi-Fi adapter" value={wifi?.adapter_description ?? wifi?.adapter_name ?? 'Not available'}/>
          <DataLine label="Wi-Fi link speed" value={wifi?.adapter_link_speed ?? 'Not available'}/>
          <DataLine label="Wi-Fi signal" value={wifi?.signal_percent != null ? `${wifi.signal_percent}%` : 'Restricted or unavailable'}/>
          <DataLine label="Wi-Fi network" value={wifi?.ssid ?? 'Unavailable'}/>
          <p className="disclaimer">{wifi?.detail ?? 'Wi-Fi details have not been collected.'}</p>
          <DataLine label="VPN routing" value={vpn?.status ?? overview.vpn}/>
          <p className="disclaimer">{vpn?.detail ?? 'Not checked.'}</p>
          <DataLine label="Proxy settings" value={proxy?.status ?? overview.proxy}/>
          <p className="disclaimer">{proxy?.detail ?? 'Not checked.'}</p>

          <div className="diagnosis-block">
            <strong>Public IP and provider</strong>
            <p>This optional check contacts IP.SB. The operator of your exit IP may be a VPN or proxy, not your subscribed ISP.</p>
            <label htmlFor="router-wan" style={{ display: 'block', marginTop: 12, fontSize: 13 }}>
              Router WAN IPv4 (optional, from your router settings)
            </label>
            <input id="router-wan" type="text" value={wanIp} maxLength={45}
              onChange={event => setWanIp(event.target.value)}
              placeholder="e.g. 100.64.12.34"
              style={{ margin: '8px 0 12px', width: '100%', maxWidth: 330,
                padding: 11, borderRadius: 8, background: '#0b1528',
                color: '#eef4ff', border: '1px solid #37506e' }}/>
            <div><button className="primary" onClick={checkPublic} disabled={publicBusy}>
              <Globe2 size={17}/>{publicBusy ? 'Checking…' : 'Check public connection'}</button></div>
            {publicError && <p className="inline-warning" role="alert">{publicError}</p>}
            {publicInfo && <div style={{ marginTop: 13 }}>
              <DataLine label="Observed public IP" value={publicInfo.public_ip}/>
              <DataLine label="IP version" value={publicInfo.ip_family}/>
              <DataLine label="Exit IP network" value={publicInfo.exit_network ?? 'Unknown'}/>
              <DataLine label="Network ASN" value={publicInfo.asn != null ? `AS${publicInfo.asn}` : 'Unknown'}/>
              <DataLine label="Local IPv4" value={publicInfo.local_ipv4 ?? 'Unknown'}/>
              <DataLine label="CGNAT / NAT clues" value={publicInfo.nat_status}/>
              <p>{publicInfo.nat_explanation}</p>
              <p className="disclaimer">{publicInfo.provider_explanation}</p>
            </div>}
          </div>

          <DataLine label="Hotspot identity" value={overview.hotspot} quiet/>
          <p className="disclaimer">No hotspot identity is inferred from SSID or Wi-Fi adapter alone.
            No router login, port scans or location permissions are required.</p>
        </section>}

        <footer><Globe2 size={14}/> Read-only diagnostics <span>·</span>
          No automatic speed test or public IP lookup <span>·</span> Speed readings stored locally</footer>
      </main>
    </div>
  );
}
