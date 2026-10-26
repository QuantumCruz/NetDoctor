
import { useEffect, useRef, useState } from 'react';
import {
  Activity, Play, Square, RefreshCw,
} from 'lucide-react';
import {
  FeedbackButton, notify, beginTask,
} from './feedback.jsx';

const PALETTE = {
  ok: '#63e8cb',
  mixed: '#f1c67a',
  failed: '#ef8f8f',
};

const EMPTY = {
  running: false,
  samples: [],
  counts: {
    ok: 0,
    mixed: 0,
    failed: 0,
  },
  message: 'No connection watch has started.',
};

function Timeline({ samples }) {
  if (!samples.length) {
    return (
      <div
        style={{
          color: '#91a7c2',
          padding: '42px 12px',
          textAlign: 'center',
        }}
      >
        Start monitoring to see a timeline of connection checks.
      </div>
    );
  }

  const width = 800;
  const step = width / Math.max(120, samples.length);

  return (
    <div
      style={{
        overflowX: 'auto',
        margin: '18px 0',
      }}
    >
      <svg
        viewBox={`0 0 ${width} 115`}
        width="100%"
        role="img"
        aria-label={`${samples.length} connection checks, oldest to newest`}
      >
        <line
          x1="0"
          x2={width}
          y1="100"
          y2="100"
          stroke="#324861"
        />

        {samples.map((sample, index) => (
          <rect
            key={`${sample.checked_at}-${index}`}
            x={index * step + 1}
            y={
              sample.state === 'failed'
                ? 29
                : sample.state === 'mixed'
                  ? 44
                  : 12
            }
            width={Math.max(3, step - 2)}
            height={
              sample.state === 'failed'
                ? 71
                : sample.state === 'mixed'
                  ? 56
                  : 88
            }
            rx="2"
            fill={
              PALETTE[sample.state] || '#7f95b2'
            }
          >
            <title>
              {`${new Date(sample.checked_at).toLocaleString()}: ${sample.state}; gateway ping: ${
                sample.gateway_reply == null
                  ? 'unknown'
                  : sample.gateway_reply
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
          'Open NetDoctor in the Windows desktop app.'
        );
      }
      return;
    }

    const finish = silent
      ? null
      : beginTask(
          'Refreshing connection history…',
          'Loading locally stored checks.'
        );

    if (!silent) setRefreshing(true);

    try {
      const next =
        await window.pywebview.api.get_stability_status();

      setState(next);

      if (!silent) {
        setError('');

        finish(
          'success',
          'History updated',
          `${next.samples?.length ?? 0} recent checks available.`
        );
      }

      if (
        mounted.current &&
        previousRunning.current &&
        !next.running &&
        next.message === 'Monitoring session completed.'
      ) {
        notify(
          'success',
          'Stability watch completed',
          'The selected session has finished.'
        );
      }

      previousRunning.current = Boolean(next.running);
    } catch {
      setError(
        'Could not read the saved connection history.'
      );

      finish?.(
        'error',
        'History refresh failed',
        'The local data could not be read.'
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
          !next.running &&
          next.message === 'Monitoring session completed.'
        ) {
          notify(
            'success',
            'Stability watch completed',
            'The selected session has finished.'
          );
        }

        previousRunning.current = Boolean(next.running);
        mounted.current = true;
      } catch {
        if (active) {
          setError('Could not read the connection history.');
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
      `Requested ${duration}-minute session.`
    );

    setPending(true);
    setError('');

    try {
      const result =
        await window.pywebview.api.start_stability_watch(
          duration
        );

      if (result?.ok) {
        finish(
          'success',
          'Stability watch started',
          `Checking public connectivity about every 10 seconds for ${duration} minutes.`
        );

        await readStatus({ silent: true });
      } else {
        const message =
          result?.message || 'Could not start monitoring.';

        setError(message);

        finish(
          'warning',
          'Monitoring not started',
          message
        );
      }
    } catch {
      setError('Could not start monitoring.');

      finish(
        'error',
        'Start failed',
        'The monitoring process did not start.'
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
      'Waiting for the current check to finish.'
    );

    setPending(true);

    try {
      const result =
        await window.pywebview.api.stop_stability_watch();

      if (result?.ok) {
        finish(
          'success',
          'Stop requested',
          'The watch will stop after the current check.'
        );

        await readStatus({ silent: true });
      } else {
        const message =
          result?.message || 'Could not stop monitoring.';

        setError(message);

        finish(
          'error',
          'Stop request failed',
          message
        );
      }
    } catch {
      setError(
        'Could not stop monitoring normally.'
      );

      finish(
        'error',
        'Stop request failed',
        'The monitor may still be running; refresh the status.'
      );
    } finally {
      setPending(false);
    }
  }

  const samples = state.samples || [];
  const counts = state.counts || EMPTY.counts;

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
        Watch for intermittent connection trouble.
        Checks run every 10 seconds without speed-test
        downloads or network-setting changes.
      </p>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 14,
          margin: '22px 0',
        }}
      >
        <label
          htmlFor="watch-duration"
          style={{
            color: '#adbed4',
            fontSize: 13,
          }}
        >
          Session length
        </label>

        <select
          id="watch-duration"
          value={duration}
          disabled={state.running || pending}
          onChange={event => {
            const value = Number(event.target.value);

            setDuration(value);

            notify(
              'info',
              'Session length selected',
              `${value} minutes. Monitoring has not started.`
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
            <Square size={16} />
            Stop monitoring
          </FeedbackButton>
        ) : (
          <FeedbackButton
            className="primary"
            disabled={!desktop || refreshing}
            busy={pending}
            onClick={start}
          >
            <Play size={16} />
            Start monitoring
          </FeedbackButton>
        )}

        <FeedbackButton
          className="text-link"
          disabled={!desktop || pending}
          busy={refreshing}
          onClick={() => readStatus()}
        >
          <RefreshCw size={16} />
          Refresh
        </FeedbackButton>
      </div>

      <p
        role="status"
        className={state.running ? 'nd-running' : ''}
        style={{
          color: state.running
            ? '#70ead2'
            : '#aebfd5',
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
        <p
          className="inline-warning"
          role="alert"
        >
          {error}
        </p>
      )}

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

            <strong
              style={{
                display: 'block',
                color,
                marginTop: 14,
                fontSize: 30,
              }}
            >
              {count}
            </strong>
          </article>
        ))}
      </div>

      <div style={{ marginTop: 24 }}>
        <strong>Recent history</strong>

        <Timeline samples={samples} />

        <div
          style={{
            display: 'flex',
            gap: 20,
            flexWrap: 'wrap',
            color: '#aebfd5',
            fontSize: 12,
          }}
        >
          {Object.entries(PALETTE).map(
            ([name, color]) => (
              <span key={name}>
                <span
                  style={{
                    display: 'inline-block',
                    background: color,
                    width: 9,
                    height: 9,
                    marginRight: 6,
                    borderRadius: 2,
                  }}
                />

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

      {samples.length > 0 && (
        <p className="disclaimer">
          Showing the latest {samples.length} saved checks
          (up to 120). Older results are retained locally
          up to 1,000 checks. A failed TCP connection is
          not proof of a general outage; gateway ping is optional.
        </p>
      )}

      <p className="disclaimer">
        Uses short TCP connections to two public destinations.
        No continuous monitoring after the selected session
        or app closes. No account, location service or remote
        storage is required.
      </p>
    </section>
  );
}
