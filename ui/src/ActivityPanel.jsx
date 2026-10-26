
import { useEffect, useState } from 'react';
import {
  Activity, Gamepad2, Film, Video, Globe2, RefreshCw, Gauge, Zap,
} from 'lucide-react';

const icons = { gaming: Gamepad2, streaming: Film, calls: Video, browsing: Globe2 };
const colors = { positive: '#63e8cb', caution: '#f1c67a', neutral: '#9bb7d5' };

function MilliCard({ label, value, color }) {
  return (
    <div className="mini-metric" style={{ display: 'block', minHeight: 105 }}>
      <span>{label}</span>
      <strong style={{ display: 'block', marginTop: 13, fontSize: 25, color }}>
        {typeof value === 'number' && Number.isFinite(value)
          ? `${value > 0 && label === 'CHANGE' ? '+' : ''}${value.toFixed(0)} ms`
          : '—'}
      </strong>
    </div>
  );
}

export default function ActivityPanel({ reading }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loadBusy, setLoadBusy] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [loadResult, setLoadResult] = useState(null);

  async function refresh() {
    if (!window.pywebview?.api?.get_activity_outlook) {
      setError('Open the Windows NetDoctor app to see activity insights.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      setResult(await window.pywebview.api.get_activity_outlook(reading ?? null));
    } catch {
      setError('The saved measurements could not be analyzed right now.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [reading?.tested_at, reading?.download_mbps, reading?.upload_mbps]);

  async function testLoadedLatency() {
    if (loadBusy) return;
    if (!window.pywebview?.api?.check_loaded_latency) {
      setLoadError('This test is available in the Windows desktop app only.');
      return;
    }
    if (!window.confirm(
      'NetDoctor will download up to 4 MiB (about 4.2 MB) from a test ' +
      'provider and send small ping requests to compare response times ' +
      'before and during the download. This may use metered mobile data. ' +
      'No settings will be changed. Continue?'
    )) return;

    setLoadBusy(true);
    setLoadError('');
    setLoadResult(null);
    try {
      const answer = await window.pywebview.api.check_loaded_latency();
      if (answer?.ok && answer.result) {
        setLoadResult(answer.result);
      } else {
        setLoadError(answer?.error || 'The loaded-latency check could not finish.');
      }
    } catch {
      setLoadError('The loaded-latency check could not finish.');
    } finally {
      setLoadBusy(false);
    }
  }

  return (
    <section className="panel details-panel" style={{ maxWidth: 1060 }}>
      <p className="eyebrow">YOUR MEASURED CONNECTION</p>
      <div className="panel-heading" style={{ alignItems: 'flex-start' }}>
        <div>
          <h2>What can this connection support?</h2>
          <p>
            Bandwidth references and latency clues from your last speed test,
            not a fabricated quality score.
          </p>
        </div>
        <button className="text-link" onClick={refresh} disabled={busy}>
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {error && <p className="inline-warning" role="alert">{error}</p>}
      {busy && <p role="status">Reading your saved measurements…</p>}
      {result && (
        <>
          <div className="diagnosis-block" style={{
            borderLeft: `4px solid ${result.stale ? '#f1c67a' : '#63e8cb'}`,
          }}>
            <strong>
              {result.stale ? 'Historical or incomplete speed reading' : 'Based on your last speed test'}
            </strong>
            <p>{result.note}</p>
            {result.tested_at && (
              <p style={{ fontSize: 12 }}>
                Measured: {new Date(result.tested_at).toLocaleString()}
              </p>
            )}
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
            gap: 15,
            margin: '23px 0',
          }}>
            {result.activities.map(item => {
              const Icon = icons[item.key] || Activity;
              const color = result.stale ? colors.neutral : colors[item.tone];
              return (
                <article key={item.key} className="panel" style={{
                  background: '#172842', borderColor: '#2a4061', padding: 20,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 15 }}>
                    <Icon color={color} size={21} />
                    <strong>{item.title}</strong>
                  </div>
                  <div style={{ color, fontWeight: 800, fontSize: 17 }}>
                    {item.status}
                  </div>
                  {result.stale && (
                    <p style={{ color: '#f1c67a', fontSize: 12 }}>
                      From an old or incomplete measurement — not current performance.
                    </p>
                  )}
                  <p>{item.detail}</p>
                </article>
              );
            })}
          </div>

          <div className="diagnosis-block">
            <strong>What the stability watch observed</strong>
            <p style={{ color: '#eaf1ff' }}>{result.stability.status}</p>
            <p>{result.stability.detail}</p>
          </div>
        </>
      )}

      <div className="diagnosis-block" style={{ marginTop: 24 }}>
        <p className="eyebrow">OPTIONAL INTERACTIVE-RESPONSE CHECK</p>
        <h2 style={{ fontSize: 23 }}>Does your connection lag during downloads?</h2>
        <p>
          A separate small download can reveal whether ping response time rises
          while the connection is busy. This is especially relevant to
          gaming and video calls, but it does not test those services directly.
        </p>
        <button className="primary" disabled={loadBusy} onClick={testLoadedLatency}>
          <Zap size={17} />
          {loadBusy ? 'Checking responsiveness…' : 'Check response under load'}
        </button>
        <p className="disclaimer">
          Only runs after confirmation. Up to 4 MiB (about 4.2 MB) downloaded,
          plus small requests. No upload stress test and no automatic repeat.
        </p>
        {loadError && <p className="inline-warning" role="alert">{loadError}</p>}
        {loadBusy && <p role="status">Comparing idle and during-download responses…</p>}

        {loadResult && (
          <div aria-live="polite" style={{ marginTop: 23 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Gauge size={22} color={colors[loadResult.tone] || colors.neutral} />
              <strong style={{ fontSize: 19 }}>{loadResult.headline}</strong>
            </div>
            <p>{loadResult.explanation}</p>
            <div className="metric-row" style={{ marginTop: 18 }}>
              <MilliCard label="IDLE PING" value={loadResult.idle_ms} color="#eaf1ff" />
              <MilliCard label="DURING DOWNLOAD" value={loadResult.during_download_ms} color="#eaf1ff" />
              <MilliCard label="CHANGE" value={loadResult.change_ms}
                color={colors[loadResult.tone] || colors.neutral} />
            </div>
            <div className="diagnosis-block action">
              <strong>What to try next</strong>
              <p>{loadResult.next_step}</p>
            </div>
            <p className="disclaimer">
              Checked {new Date(loadResult.tested_at).toLocaleString()} ·
              {' '}{loadResult.received_mib} MiB downloaded ·
              {' '}{loadResult.loaded_replies} replies overlapped the transfer.
              These results are from this run, not a permanent live reading.
            </p>
            <p className="disclaimer">{loadResult.limitation}</p>
          </div>
        )}
      </div>

      <p className="disclaimer">
        Opening Activities doesn't start any measurement. Existing speed and
        stability history may describe a different time or network. Actual
        game servers, streaming services, websites and calls were not tested.
      </p>
      <p className="disclaimer">
        Bandwidth references: Netflix streaming and Zoom HD video guidance.
      </p>
    </section>
  );
}
