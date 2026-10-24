
import { useEffect, useState } from 'react';
import {
  Activity,
  Play,
  Square,
  RefreshCw,
} from 'lucide-react';

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
  message: 'No saved connection checks yet.',
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
        margin: '16px 0',
      }}
    >
      <svg
        viewBox={`0 0 ${width} 115`}
        width="100%"
        role="img"
        aria-label={`${samples.length} recent connection checks, oldest to newest`}
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
              {`${new Date(sample.checked_at).toLocaleString()}: ${sample.state}; gateway echo ${
                sample.gateway_reply === null
                  ? 'not checked'
                  : sample.gateway_reply
                    ? 'replied'
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
  const [error, setError] = useState('');

  const desktop = Boolean(
    window.pywebview?.api?.get_stability_status
  );

  async function refresh() {
    if (
      !window.pywebview?.api?.get_stability_status
    ) {
      return;
    }

    try {
      setState(
        await window.pywebview.api.get_stability_status()
      );
    } catch {
      setError(
        'Could not read the saved connection history.'
      );
    }
  }

  useEffect(() => {
    let active = true;

    const poll = async () => {
      if (
        !window.pywebview?.api?.get_stability_status
      ) {
        return;
      }

      try {
        const next =
          await window.pywebview.api.get_stability_status();

        if (active) {
          setState(next);
        }
      } catch {
        if (active) {
          setError(
            'Could not read the connection history.'
          );
        }
      }
    };

    poll();

    const handle = window.setInterval(
      poll,
      3000,
    );

    return () => {
      active = false;
      window.clearInterval(handle);
    };
  }, []);

  async function start() {
    if (
      !window.pywebview?.api?.start_stability_watch
      || pending
    ) {
      return;
    }

    setError('');
    setPending(true);

    try {
      const response =
        await window.pywebview.api.start_stability_watch(
          duration
        );

      if (!response?.ok) {
        setError(
          response?.message
          || 'Could not start monitoring.'
        );
      }

      await refresh();
    } catch {
      setError(
        'Could not start monitoring.'
      );
    } finally {
      setPending(false);
    }
  }

  async function stop() {
    if (
      !window.pywebview?.api?.stop_stability_watch
      || pending
    ) {
      return;
    }

    setPending(true);

    try {
      const response =
        await window.pywebview.api.stop_stability_watch();

      if (!response?.ok) {
        setError(
          response?.message
          || 'Could not stop monitoring.'
        );
      }

      await refresh();
    } catch {
      setError(
        'Could not stop monitoring normally.'
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
        Checks run every 10 seconds, without speed-test
        downloads or changing network settings.
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
          onChange={event => setDuration(
            Number(event.target.value)
          )}
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
          <button
            className="primary"
            disabled={pending}
            onClick={stop}
          >
            <Square size={16} />
            Stop monitoring
          </button>
        ) : (
          <button
            className="primary"
            disabled={!desktop || pending}
            onClick={start}
          >
            <Play size={16} />
            Start monitoring
          </button>
        )}

        <button
          className="text-link"
          onClick={refresh}
          disabled={!desktop || pending}
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      <p
        role="status"
        style={{
          color: state.running
            ? '#70ead2'
            : '#aebfd5',
        }}
      >
        <Activity
          size={15}
          style={{
            verticalAlign: 'middle',
            marginRight: 8,
          }}
        />

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
          [
            'Both checks connected',
            counts.ok,
            PALETTE.ok,
          ],
          [
            'One connected',
            counts.mixed,
            PALETTE.mixed,
          ],
          [
            'Neither connected',
            counts.failed,
            PALETTE.failed,
          ],
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
          not proof of a general internet outage.
          Gateway ping replies are optional and do not
          prove Wi-Fi quality. Repeating failures may
          warrant further diagnosis.
        </p>
      )}

      <p className="disclaimer">
        Uses short TCP connections to two public destinations.
        No continuous monitoring after the selected session
        expires or after the app exits. No account, location
        service, or remote storage is required.
      </p>
    </section>
  );
}
