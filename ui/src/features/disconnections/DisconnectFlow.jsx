import { confirmInPage } from '../../confirmInPage.mjs';

import { useEffect, useRef, useState } from 'react';
import {
  Activity,
  ArrowLeft,
  Play,
  RotateCcw,
  ShieldCheck,
  Square,
} from 'lucide-react';

import { analyzeDisconnects } from './disconnectAnalysis.mjs';

function Bubble({ mine = false, children }) {
  return (
    <div className={`guided-message ${mine ? 'guided-mine' : ''}`}>
      {!mine && (
        <span className="guided-avatar">
          <Activity size={18} />
        </span>
      )}
      <div className="guided-bubble">{children}</div>
    </div>
  );
}

export default function DisconnectFlow({ onBack }) {
  const [startedAt, setStartedAt] = useState(null);
  const [status, setStatus] = useState(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  const busy = useRef(false);

  useEffect(() => {
    if (!startedAt) return undefined;

    let active = true;
    let fetching = false;
    let timer;

    async function refresh() {
      if (!active || fetching) return;

      fetching = true;

      try {
        const result =
          await window.pywebview.api.get_stability_status();

        if (!active) return;

        setStatus(result);
        setError('');

        if (!result.running && timer) {
          clearInterval(timer);
          timer = null;
        }
      } catch {
        if (active) {
          setError(
            'Could not refresh the connection watch. ' +
            'The watch may still be running.'
          );
        }
      } finally {
        fetching = false;
      }
    }

    timer = setInterval(refresh, 3000);
    void refresh();

    return () => {
      active = false;
      if (timer) clearInterval(timer);
    };
  }, [startedAt]);

  async function start() {
    if (busy.current) return;

    const api = window.pywebview?.api;

    if (
      !api?.start_stability_watch ||
      !api?.get_stability_status ||
      !api?.stop_stability_watch
    ) {
      setError(
        'Open the NetDoctor Windows app to monitor your connection.'
      );
      return;
    }

    if (!(await confirmInPage({ title: 'Monitor connection stability?', message: ('NetDoctor will attempt short internet connections to ' +
      '1.1.1.1 and 8.8.8.8 about every 10 seconds for five minutes ' +
      'and optionally ping your router. Those destinations can see ' +
      'your public IP. No speed-test files will be downloaded or ' +
      'network settings changed. Start monitoring?').replace(/\s+(?:Continue\?|Start monitoring\?)$/, ''), confirmLabel: 'Start monitoring' }))) {
      return;
    }

    busy.current = true;
    setPending(true);
    setError('');

    const since = new Date().toISOString();

    try {
      const response =
        await api.start_stability_watch(5);

      if (!response?.ok) {
        setError(
          response?.message || 'The watch could not start.'
        );
        return;
      }

      setStartedAt(since);
      setStatus({
        running: true,
        message: 'Monitoring in progress.',
        samples: [],
      });
    } catch {
      setError(
        'The watch could not start. Please try again.'
      );
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  async function stop() {
    if (busy.current || !status?.running) return;

    busy.current = true;
    setPending(true);
    setError('');

    try {
      const response =
        await window.pywebview.api.stop_stability_watch();

      if (!response?.ok) {
        setError(
          response?.message || 'The stop request failed.'
        );
      }
    } catch {
      setError('The stop request could not finish.');
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  const analysis =
    startedAt && status
      ? analyzeDisconnects(status, startedAt)
      : null;

  return (
    <main className="guided-main">
      <header className="guided-header">
        <div>
          <p className="guided-eyebrow">
            GUIDED CONNECTION WATCH
          </p>
          <h1>Why does my internet keep disconnecting?</h1>
          <p>
            Record what actually happens when your connection drops.
          </p>
        </div>

        <button
          type="button"
          className="guided-restart"
          onClick={onBack}
          disabled={pending}
        >
          <ArrowLeft size={16} />
          All questions
        </button>
      </header>

      <section
        className="guided-chat"
        aria-label="Connection disconnection troubleshooting"
        aria-busy={pending}
      >
        <Bubble mine>
          Why does my internet keep disconnecting?
        </Bubble>

        <Bubble>
          <strong>
            Let's monitor your connection.
          </strong>

          <p>
            NetDoctor can run small checks every 10 seconds
            and record when internet destinations stop responding.
          </p>

          <p>
            No speed test, downloads or router configuration needed.
          </p>

          {!startedAt && (
            <div className="guided-buttons">
              <button
                type="button"
                className="guided-primary"
                disabled={pending}
                onClick={start}
              >
                <Play size={16} />
                {pending
                  ? 'Starting…'
                  : 'Start 5-minute watch'}
              </button>
            </div>
          )}

          {error && (
            <p className="guided-error" role="alert">
              {error}
            </p>
          )}
        </Bubble>

        {analysis && (
          <Bubble>
            <strong className="guided-answer-title">
              {analysis.headline}
            </strong>

            <p role="status">
              {status.running
                ? 'Monitoring now — refreshing automatically.'
                : status.message}
            </p>

            <div className="guided-next-step">
              <strong>
                What NetDoctor observed
              </strong>

              {analysis.facts.map(fact => (
                <p key={fact}>{fact}</p>
              ))}
            </div>

            {analysis.lastCheckedAt && (
              <p className="guided-caution">
                Last check:{' '}
                {new Date(
                  analysis.lastCheckedAt
                ).toLocaleTimeString()}
              </p>
            )}

            <p>
              <strong>What to do next</strong>
            </p>

            <p>{analysis.next}</p>

            <p className="guided-caution">
              {analysis.note}
            </p>

            {status.history_notice && (
              <details className="guided-details">
                <summary>
                  How the checks are separated
                </summary>

                <p>{status.history_notice}</p>

                <p>
                  Only samples recorded since this guided
                  watch began are included above.
                </p>
              </details>
            )}

            <div className="guided-buttons">
              {status.running ? (
                <button
                  type="button"
                  className="guided-secondary"
                  onClick={stop}
                  disabled={pending}
                >
                  <Square size={16} />
                  {pending
                    ? 'Stopping…'
                    : 'Stop watch'}
                </button>
              ) : (
                <button
                  type="button"
                  className="guided-primary"
                  onClick={start}
                  disabled={pending}
                >
                  <RotateCcw size={16} />
                  Watch again
                </button>
              )}
            </div>
          </Bubble>
        )}
      </section>

      <footer className="guided-footer">
        <ShieldCheck size={16} />
        If you leave this page, an active watch continues
        until its selected time limit or you stop it in
        Stability tools.
      </footer>
    </main>
  );
}
