import { confirmInPage } from '../../confirmInPage.mjs';

import { useRef, useState } from 'react';
import {
  Activity,
  ArrowLeft,
  Cloud,
  ShieldCheck,
} from 'lucide-react';

import { rankRegionalProbes } from './vpsLatency.mjs';

export default function VpsFinderFlow({ onBack }) {
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const running = useRef(false);

  async function measure() {
    if (running.current) return;

    const api = window.pywebview?.api;

    if (!api?.check_cloud_regions) {
      setError(
        'Open NetDoctor in its Windows desktop window ' +
        'to run this check.'
      );
      return;
    }

    if (!(await confirmInPage({ title: 'Measure cloud latency?', message: ('NetDoctor will connect to preset AWS and Oracle ' +
      'HTTPS API endpoints. The services can see your ' +
      'public IP. No VPS will be created and no cloud ' +
      'charges will be incurred. Continue?').replace(/\s+(?:Continue\?|Start monitoring\?)$/, ''), confirmLabel: 'Measure regions' }))) {
      return;
    }

    running.current = true;
    setBusy(true);
    setError('');
    setReport(null);

    try {
      const response =
        await api.check_cloud_regions('all');

      if (
        !response?.ok ||
        !Array.isArray(response.report?.results)
      ) {
        setError(
          response?.error ||
          'No usable regional measurement was returned.'
        );
      } else {
        setReport(response.report);
      }
    } catch {
      setError(
        'Regional measurements could not be completed.'
      );
    } finally {
      running.current = false;
      setBusy(false);
    }
  }

  const ranked = rankRegionalProbes(report);

  return (
    <main className="guided-main">
      <header className="guided-header">
        <div>
          <p className="guided-eyebrow">
            CLOUD REGION RESPONSIVENESS
          </p>

          <h1>
            Which VPS location has the lowest latency?
          </h1>

          <p>
            Measure regional network responsiveness
            from this computer.
          </p>
        </div>

        <button
          className="guided-restart"
          type="button"
          disabled={busy}
          onClick={onBack}
        >
          <ArrowLeft size={16} />
          All questions
        </button>
      </header>

      <section
        className="guided-chat"
        aria-label="Regional latency comparison"
        aria-busy={busy}
      >
        <div className="guided-message">
          <span className="guided-avatar">
            <Activity size={18} />
          </span>

          <div className="guided-bubble">
            <strong>
              Find the fastest measured cloud endpoint.
            </strong>

            <p>
              NetDoctor tests AWS and Oracle regional
              API endpoints using TCP port 443.
              This is not actual VPS ping or a server
              performance test.
            </p>

            <div className="guided-buttons">
              <button
                type="button"
                className="guided-primary"
                onClick={measure}
                disabled={busy}
              >
                <Cloud size={16} />

                {busy
                  ? 'Measuring…'
                  : report
                    ? 'Measure again'
                    : 'Measure regional latency'}
              </button>
            </div>

            {error && (
              <p
                className="guided-error"
                role="alert"
              >
                {error}
              </p>
            )}
          </div>
        </div>

        {report && (
          <div className="guided-message">
            <span className="guided-avatar">
              <Activity size={18} />
            </span>

            <div
              className="guided-bubble"
              aria-live="polite"
            >
              {ranked.length ? (
                <>
                  <strong className="guided-answer-title">
                    Fastest measured:{' '}
                    {ranked[0].median_ms.toFixed(1)} ms
                  </strong>

                  <p>
                    {ranked[0].provider}
                    {' · '}
                    {ranked[0].location}
                    {' · '}
                    {ranked[0].successful}/
                    {ranked[0].attempts}
                    {' TCP connections completed.'}
                  </p>

                  <details className="guided-details">
                    <summary>
                      Compare the other tested regions
                    </summary>

                    {ranked.slice(1).map(item => (
                      <p
                        key={`${item.provider}-${item.region}`}
                      >
                        {item.provider}
                        {' · '}
                        {item.location}
                        {': '}
                        {item.median_ms.toFixed(1)} ms
                        {' ('}
                        {item.successful}/{item.attempts}
                        {' connections)'}
                      </p>
                    ))}
                  </details>
                </>
              ) : (
                <strong>
                  No endpoint had enough successful
                  measurements to rank.
                </strong>
              )}

              <p className="guided-caution">
                These are short TCP handshakes to cloud
                API endpoints, not deployed VPS instances.
                The fastest measured region is a candidate
                to investigate, not a guaranteed
                VPS-latency winner.
              </p>
            </div>
          </div>
        )}
      </section>

      <footer className="guided-footer">
        <ShieldCheck size={16} />
        Tests are opt-in.
        No pricing or performance guesses.
      </footer>
    </main>
  );
}
