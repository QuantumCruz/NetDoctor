import { useEffect, useRef, useState } from 'react';
import { Activity, Play, Square, RefreshCw, Archive } from 'lucide-react';
import { FeedbackButton, notify, beginTask } from './feedback.jsx';

const PALETTE = {
  ok: '#63e8cb',
  mixed: '#f1c67a',
  failed: '#ef8f8f',
};

const EMPTY = {
  running: false,
  samples: [],
  counts: { ok: 0, mixed: 0, failed: 0 },
  message: 'No connection watch has started.',
  history_scope: 'unverified',
  history_notice: 'Previous history is not assigned to the current connection.',
  other_network_count: 0,
};

function Timeline({ samples }) {
  if (!samples.length) {
    return (
      <p style={{
        color: '#91a7c2',
        padding: '28px 10px',
        textAlign: 'center',
      }}>
        No checks recorded for this connection yet.
        Start a watch to create a timeline.
      </p>
    );
  }

  const width = 800;
  const step = width / Math.max(120, samples.length);

  return (
    <div style={{ overflowX: 'auto', margin: '18px 0' }}>
      <svg
        viewBox={`0 0 ${width} 115`}
        width="100%"
        role="img"
        aria-label={`${samples.length} current-connection checks, oldest to newest`}
      >
        <line
          x1="0"
          x2={width}
          y1="100"
          y2="100"
          stroke="#324861"
        />

        {samples.map((item, index) => (
          <rect
            key={`${item.checked_at}-${index}`}
            x={index * step + 1}
            y={
              item.state === 'failed'
                ? 29
                : item.state === 'mixed'
                  ? 44
                  : 12
            }
            width={Math.max(3, step - 2)}
            height={
              item.state === 'failed'
                ? 71
                : item.state === 'mixed'
                  ? 56
                  : 88
            }
            rx="2"
            fill={PALETTE[item.state] || '#7f95b2'}
          >
            <title>
              {`${new Date(item.checked_at).toLocaleString()}: ${item.state}; gateway ping: ${
                item.gateway_reply == null
                  ? 'unknown'
                  : item.gateway_reply
                    ? 'reply'
                    : 'no reply'
              }`}
            </title>
          </rect>
        ))}
      </svg>
    </div>
  );
}

export default function StabilityPanel() {
  const [state, setState] = useState(EMPTY);
  const [duration, setDuration] = useState(10);
  const [pending, setPending] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const previousRunning = useRef(false);
  const mounted = useRef(false);

  const desktop = Boolean(
    window.pywebview?.api?.get_stability_status
  );

  async function readStatus({ silent = false } = {}) {
    if (!window.pywebview?.api?.get_stability_status) {
      if (!silent) {
        notify(
          'warning',
          'History unavailable',
          'Open the Windows desktop app.'
        );
      }
      return;
    }

    const finish = silent
      ? null
      : beginTask(
          'Refreshing connection history…',
          'Reading locally saved checks.'
        );

    if (!silent) setRefreshing(true);

    try {
      const next =
        await window.pywebview.api.get_stability_status();

      setState(next);
      setError('');

      if (!silent) {
        finish(
          'success',
          'History updated',
          `${next.samples?.length ?? 0} checks for this connection.`
        );
      }

      if (
        mounted.current &&
        previousRunning.current &&
        !next.running
      ) {
        if (next.message === 'Monitoring session completed.') {
          notify(
            'success',
            'Stability watch completed',
            'The selected monitoring session finished.'
          );
        } else if (next.message?.includes('configuration changed')) {
          notify(
            'warning',
            'Monitoring ended after network change',
            'Results were not mixed across connections.'
          );
        }
      }

      previousRunning.current = Boolean(next.running);
      mounted.current = true;

    } catch {
      setError(
        'Could not read the saved connection history.'
      );

      finish?.(
        'error',
        'History refresh failed',
        'Local connection history could not be read.'
      );
    } finally {
      if (!silent) setRefreshing(false);
    }
  }

  useEffect(() => {
    let active = true;
    mounted.current = false;

    async function poll() {
      if (
        !window.pywebview?.api?.get_stability_status ||
        !active
      ) {
        return;
      }

      try {
        const next =
          await window.pywebview.api.get_stability_status();

        if (!active) return;

        setState(next);

        if (
          mounted.current &&
          previousRunning.current &&
          !next.running
        ) {
          if (next.message === 'Monitoring session completed.') {
            notify(
              'success',
              'Stability watch completed',
              'The selected session has finished.'
            );
          } else if (next.message?.includes('configuration changed')) {
            notify(
              'warning',
              'Network configuration changed',
              'The current watch was stopped automatically.'
            );
          }
        }

        previousRunning.current = Boolean(next.running);
        mounted.current = true;

      } catch {
        if (active) {
          setError(
            'Could not read the connection history.'
          );
        }
      }
    }

    poll();

    const timer = window.setInterval(poll, 3000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  async function start() {
    if (
      pending ||
      !window.pywebview?.api?.start_stability_watch
    ) {
      return;
    }

    const finish = beginTask(
      'Starting stability watch…',
      `${duration}-minute session requested.`
    );

    setPending(true);
    setError('');

    try {
      const answer =
        await window.pywebview.api.start_stability_watch(
          duration
        );

      if (answer?.ok) {
        finish(
          'success',
          'Stability watch started',
          'Checking connectivity about every 10 seconds.'
        );

        await readStatus({ silent: true });
      } else {
        setError(
          answer?.message || 'Could not start monitoring.'
        );

        finish(
          'warning',
          'Monitoring not started',
          answer?.message || 'No session started.'
        );
      }

    } catch {
      setError('Could not start monitoring.');

      finish(
        'error',
        'Start failed',
        'The watch could not be started.'
      );

    } finally {
      setPending(false);
    }
  }

  async function stop() {
    if (
      pending ||
      !window.pywebview?.api?.stop_stability_watch
    ) {
      return;
    }

    const finish = beginTask(
      'Requesting monitor stop…',
      'Waiting for the active check to finish.'
    );

    setPending(true);

    try {
      const answer =
        await window.pywebview.api.stop_stability_watch();

      if (answer?.ok) {
        finish(
          'success',
          'Stop requested',
          'The monitor will finish its current check.'
        );

        await readStatus({ silent: true });

      } else {
        setError(
          answer?.message || 'Could not stop monitoring.'
        );

        finish(
          'error',
          'Stop request failed',
          answer?.message || 'Try refreshing status.'
        );
      }

    } catch {
      setError(
        'Could not stop monitoring normally.'
      );

      finish(
        'error',
        'Stop request failed',
        'The monitor may still be active.'
      );

    } finally {
      setPending(false);
    }
  }

  const samples = state.samples || [];
  const counts = state.counts || EMPTY.counts;
  const scope = state.history_scope || 'unverified';

  return (
    <section
      className="panel details-panel"
      style={{ maxWidth: 1080 }}
    >
      <p className="eyebrow">
        LOCAL CONNECTION HISTORY
      </p>

      <h2>Connection stability</h2>

      <p>
        Watch for intermittent trouble with small connection
        checks every 10 seconds. No speed-test downloads or
        network-setting changes.
      </p>

      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 14,
        margin: '22px 0',
      }}>
        <label
          htmlFor="watch-duration"
          style={{ color: '#adbed4', fontSize: 13 }}
        >
          Session length
        </label>

        <select
          id="watch-duration"
          value={duration}
          disabled={state.running || pending}
          onChange={event => {
            const n = Number(event.target.value);
            setDuration(n);
            notify(
              'info',
              'Duration selected',
              `${n} minutes. Monitoring has not started.`
            );
          }}
          style={{
            padding: 11,
            color: '#eaf1ff',
            background: '#0b1528',
            border: '1px solid #35506f',
            borderRadius: 9,
          }}
        >
          <option value={5}>5 minutes</option>
          <option value={10}>10 minutes</option>
          <option value={30}>30 minutes</option>
        </select>

        {state.running ? (
          <FeedbackButton
            className="primary"
            disabled={!desktop || refreshing}
            busy={pending}
            onClick={stop}
          >
            <Square size={16} /> Stop monitoring
          </FeedbackButton>
        ) : (
          <FeedbackButton
            className="primary"
            disabled={!desktop || refreshing}
            busy={pending}
            onClick={start}
          >
            <Play size={16} /> Start monitoring
          </FeedbackButton>
        )}

        <FeedbackButton
          className="text-link"
          disabled={!desktop || pending}
          busy={refreshing}
          onClick={() => readStatus()}
        >
          <RefreshCw size={16} /> Refresh
        </FeedbackButton>
      </div>

      <p
        role="status"
        className={state.running ? 'nd-running' : ''}
        style={{
          color: state.running ? '#70ead2' : '#aebfd5',
        }}
      >
        {!state.running && (
          <Activity
            size={15}
            style={{
              verticalAlign: 'middle',
              marginRight: 8,
            }}
          />
        )}

        {desktop
          ? state.message
          : 'Open the Windows desktop app to start monitoring.'}
      </p>

      {error && (
        <p className="inline-warning" role="alert">
          {error}
        </p>
      )}

      <div
        className="diagnosis-block"
        style={{ marginTop: 18 }}
      >
        <strong>
          {scope === 'current'
            ? 'Current connection history'
            : scope === 'session'
              ? 'This monitoring session only'
              : 'Connection could not be identified'}
        </strong>

        <p>
          {state.history_notice || EMPTY.history_notice}
        </p>

        {(state.other_network_count ?? 0) > 0 && (
          <p style={{
            display: 'flex',
            gap: 8,
            alignItems: 'center',
          }}>
            <Archive size={16} />

            {state.other_network_count} earlier or
            other-network checks are retained locally,
            but excluded from these figures.
          </p>
        )}
      </div>

      <div
        className="metric-row"
        style={{ marginTop: 23 }}
      >
        {[
          ['Both checks connected', counts.ok, PALETTE.ok],
          ['One connected', counts.mixed, PALETTE.mixed],
          ['Neither connected', counts.failed, PALETTE.failed],
        ].map(([label, count, color]) => (
          <article
            className="mini-metric"
            key={label}
            style={{ display: 'block' }}
          >
            <span>{label}</span>

            <strong style={{
              display: 'block',
              color,
              marginTop: 14,
              fontSize: 30,
            }}>
              {count}
            </strong>
          </article>
        ))}
      </div>

      <div style={{ marginTop: 24 }}>
        <strong>
          Recent checks on this connection
        </strong>

        <Timeline samples={samples} />

        <div style={{
          display: 'flex',
          gap: 20,
          flexWrap: 'wrap',
          color: '#aebfd5',
          fontSize: 12,
        }}>
          {Object.entries(PALETTE).map(
            ([name, color]) => (
              <span key={name}>
                <span style={{
                  display: 'inline-block',
                  background: color,
                  width: 9,
                  height: 9,
                  marginRight: 6,
                  borderRadius: 2,
                }} />

                {name === 'ok'
                  ? 'Both connected'
                  : name === 'mixed'
                    ? 'One connected'
                    : 'Neither connected'}
              </span>
            )
          )}
        </div>
      </div>

      <p className="disclaimer">
        Up to 120 checks are displayed, with 1,000 stored
        across all connections. Previous unassigned history
        is preserved. A failed TCP check does not prove an
        ISP outage. Route details may repeat on different
        physical networks.
      </p>

      <p className="disclaimer">
        Monitoring stops at the selected session limit,
        on app exit, or after a detected route change.
        No background downloads or subscriptions.
      </p>
    </section>
  );
}