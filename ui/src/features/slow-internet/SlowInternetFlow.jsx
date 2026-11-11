import { confirmInPage } from '../../confirmInPage.mjs';

import { useEffect, useRef, useState } from 'react';
import SpeedTest from '@cloudflare/speedtest';
import { Activity, ArrowLeft, RotateCcw, ShieldCheck, Zap } from 'lucide-react';
import { explainSpeed, readSpeed, validPlan } from './slowInternet.mjs';
import SpeedComparison from './SpeedComparison.jsx';

const MEASUREMENTS = [
  { type: 'latency', numPackets: 6 },
  { type: 'download', bytes: 100_000, count: 2, bypassMinDuration: true },
  { type: 'download', bytes: 1_000_000, count: 3, bypassMinDuration: true },
  { type: 'download', bytes: 4_000_000, count: 2, bypassMinDuration: true },
  { type: 'upload', bytes: 100_000, count: 2, bypassMinDuration: true },
  { type: 'upload', bytes: 1_000_000, count: 3, bypassMinDuration: true },
  { type: 'upload', bytes: 4_000_000, count: 2, bypassMinDuration: true },
];

function Bubble({ mine = false, children }) {
  return (
    <div className={`guided-message ${mine ? 'guided-mine' : ''}`}>
      {!mine && <span className="guided-avatar"><Activity size={18} /></span>}
      <div className="guided-bubble">{children}</div>
    </div>
  );
}

export default function SlowInternetFlow({ onBack }) {
  const [plan, setPlan] = useState('');
  const [first, setFirst] = useState(null);
  const [firstOverview, setFirstOverview] = useState(null);
  const [second, setSecond] = useState(null);
  const [secondOverview, setSecondOverview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [warning, setWarning] = useState('');
  const [testKind, setTestKind] = useState(null);

  const testerRef = useRef(null);
  const timeoutRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
      const tester = testerRef.current;
      testerRef.current = null;
      try { tester?.pause?.(); } catch { /* Shutting down. */ }
    };
  }, []);

  function stopTracking(tester) {
    if (testerRef.current !== tester) return false;
    testerRef.current = null;
    clearTimeout(timeoutRef.current);
    timeoutRef.current = null;
    return true;
  }

  function clearResults() {
    if (busy) return;
    setFirst(null);
    setFirstOverview(null);
    setSecond(null);
    setSecondOverview(null);
    setError('');
    setWarning('');
  }

  async function runTest(kind = 'first') {
    if (testerRef.current || busy) return;
    if (kind === 'first' && !validPlan(plan)) return;
    if (kind === 'second' && !first) return;

    const api = window.pywebview?.api;
    if (!api?.get_overview || !api?.save_speed) {
      setError('Open NetDoctor in its Windows app to run this test.');
      return;
    }

    const message = kind === 'second'
      ? 'Run a second speed test on this same computer using Ethernet. Make sure Wi-Fi is disconnected and the cable goes to the same router. This transfers up to about 22.4 MB plus overhead, which can use metered data. Continue?'
      : 'Measure this connection using Cloudflare. The test transfers up to about 22.4 MB plus overhead (download and upload), which can use metered data. No network settings will be changed. Continue?';

    if (!(await confirmInPage({ title: 'Run internet speed test?', message: (message).replace(/\s+(?:Continue\?|Start monitoring\?)$/, ''), confirmLabel: 'Run speed test' }))) return;

    setBusy(true);
    setTestKind(kind);
    setError('');
    setWarning('');
    if (kind === 'first') {
      setFirst(null);
      setFirstOverview(null);
      setSecond(null);
      setSecondOverview(null);
    }
    else {
      setSecond(null);
      setSecondOverview(null);
    }

    let tester;
    try {
      tester = new SpeedTest({
        autoStart: false,
        measurements: MEASUREMENTS,
        measureDownloadLoadedLatency: false,
        measureUploadLoadedLatency: false,
      });
      testerRef.current = tester;

      tester.onFinish = async results => {
        if (!stopTracking(tester) || !mountedRef.current) return;
        const measurement = readSpeed(results);
        if (measurement.download_mbps === null || measurement.upload_mbps === null) {
          setError('The test did not finish both transfers. No incomplete result was used.');
          setBusy(false);
          setTestKind(null);
          return;
        }

        let currentOverview = null;
        const messages = [];
        try {
          currentOverview = await api.get_overview();
        } catch {
          messages.push('Windows network details were not available.');
        }
        try {
          await api.save_speed(measurement);
        } catch {
          messages.push('The measured speed could not be saved to history.');
        }

        if (!mountedRef.current) return;
        if (kind === 'first') {
          setFirst(measurement);
          setFirstOverview(currentOverview);
        } else {
          setSecond(measurement);
          setSecondOverview(currentOverview);
        }
        setWarning(messages.join(' '));
        setBusy(false);
        setTestKind(null);
      };

      timeoutRef.current = window.setTimeout(() => {
        if (!stopTracking(tester)) return;
        try { tester.pause?.(); } catch { /* Already stopped. */ }
        if (!mountedRef.current) return;
        setError('The test exceeded 90 seconds and stopped. No incomplete reading was used.');
        setBusy(false);
        setTestKind(null);
      }, 90000);

      tester.play();
    } catch {
      if (tester && stopTracking(tester)) {
        try { tester.pause?.(); } catch { /* Startup failed. */ }
      }
      if (!mountedRef.current) return;
      setError('The speed test could not start. Check your connection and try again.');
      setBusy(false);
      setTestKind(null);
    }
  }

  const analysis = first ? explainSpeed(first, plan, firstOverview) : null;

  return (
    <main className="guided-main">
      <header className="guided-header">
        <div>
          <p className="guided-eyebrow">GUIDED INTERNET SPEED CHECK</p>
          <h1>Why is my internet slow?</h1>
          <p>Measure first, then compare to narrow down the problem.</p>
        </div>
        <button type="button" className="guided-restart" onClick={onBack} disabled={busy}>
          <ArrowLeft size={16} /> All questions
        </button>
      </header>

      <section className="guided-chat" aria-label="Slow internet troubleshooting" aria-busy={busy}>
        <Bubble mine>Why is my internet slow?</Bubble>
        <Bubble>
          <strong>Let's measure your connection.</strong>
          <p>What download speed does your plan advertise? Leave blank if you don't know.</p>
          <div className="guided-wan-form">
            <label htmlFor="slow-plan">Advertised download speed (Mbps, optional)</label>
            <input
              id="slow-plan" type="text" inputMode="decimal"
              value={plan} disabled={busy}
              onChange={event => {
                setPlan(event.target.value);
                clearResults();
              }}
              placeholder="Your plan's download speed"
            />
            {!validPlan(plan) && <small className="guided-error">Enter a positive number up to 100000, or leave blank.</small>}
            <div className="guided-buttons">
              <button type="button" className="guided-primary" disabled={busy || !validPlan(plan)} onClick={() => runTest('first')}>
                <Zap size={17} /> {busy && testKind === 'first' ? 'Measuring…' : 'Run first speed test'}
              </button>
            </div>
          </div>
          <p className="guided-caution">Each test transfers about 22.4 MB plus overhead. Tests run only after you confirm.</p>
          {busy && <p role="status">{testKind === 'second' ? 'Running the Ethernet comparison…' : 'Measuring your connection…'}</p>}
          {error && <p className="guided-error" role="alert">{error}</p>}
        </Bubble>

        {analysis && (
          <Bubble>
            <strong className="guided-answer-title">{analysis.headline}</strong>
            <p><strong>Evidence from your first test</strong></p>
            {analysis.facts.map(fact => <p key={fact}>{fact}</p>)}
            <div className="guided-next-step">
              <strong>What to check next</strong>
              <p>{analysis.next}</p>
            </div>
            <p className="guided-caution">{analysis.caution}</p>
            <SpeedComparison
              first={first}
              firstOverview={firstOverview}
              second={second}
              secondOverview={secondOverview}
              busy={busy}
              onTest={() => runTest('second')}
            />
            {warning && <p className="guided-error" role="status">{warning}</p>}
            <div className="guided-buttons">
              <button type="button" className="guided-secondary" onClick={clearResults} disabled={busy}>
                <RotateCcw size={16} /> Clear results
              </button>
            </div>
          </Bubble>
        )}
      </section>

      <footer className="guided-footer">
        <ShieldCheck size={16} /> Measurements are real; conclusions show what was verified.
      </footer>
    </main>
  );
}
