
import { useEffect, useState } from 'react';
import {
  Activity,
  Gamepad2,
  Film,
  Video,
  Globe2,
  RefreshCw,
} from 'lucide-react';

const icons = {
  gaming: Gamepad2,
  streaming: Film,
  calls: Video,
  browsing: Globe2,
};

const colors = {
  positive: '#63e8cb',
  caution: '#f1c67a',
  neutral: '#9bb7d5',
};

export default function ActivityPanel({ reading }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function refresh() {
    if (!window.pywebview?.api?.get_activity_outlook) {
      setError(
        'Open the Windows NetDoctor app to see your activity insights.'
      );
      return;
    }

    setBusy(true);
    setError('');

    try {
      const next = await window.pywebview.api.get_activity_outlook(
        reading ?? null
      );
      setResult(next);
    } catch {
      setError(
        'The saved measurements could not be analyzed right now.'
      );
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [
    reading?.tested_at,
    reading?.download_mbps,
    reading?.upload_mbps,
  ]);

  return (
    <section
      className="panel details-panel"
      style={{ maxWidth: 1060 }}
    >
      <p className="eyebrow">YOUR MEASURED CONNECTION</p>

      <div
        className="panel-heading"
        style={{ alignItems: 'flex-start' }}
      >
        <div>
          <h2>What can this connection support?</h2>
          <p>
            Simple bandwidth references and latency clues based
            on your last test, not a fabricated quality score.
          </p>
        </div>

        <button
          className="text-link"
          onClick={refresh}
          disabled={busy}
        >
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {error && (
        <p className="inline-warning" role="alert">
          {error}
        </p>
      )}

      {busy && (
        <p role="status">
          Reading your saved measurements…
        </p>
      )}

      {result && (
        <>
          <div
            className="diagnosis-block"
            style={{
              borderLeft: `4px solid ${
                result.stale ? '#f1c67a' : '#63e8cb'
              }`,
            }}
          >
            <strong>
              {result.stale
                ? 'Earlier or incomplete measurement'
                : 'Based on your last speed test'}
            </strong>

            <p>{result.note}</p>

            {result.tested_at && (
              <p style={{ fontSize: 12 }}>
                Measured: {
                  new Date(result.tested_at).toLocaleString()
                }
              </p>
            )}
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns:
                'repeat(auto-fit, minmax(250px, 1fr))',
              gap: 15,
              margin: '23px 0',
            }}
          >
            {result.activities.map(item => {
              const Icon = icons[item.key] || Activity;

              return (
                <article
                  key={item.key}
                  className="panel"
                  style={{
                    background: '#172842',
                    borderColor: '#2a4061',
                    padding: 20,
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      marginBottom: 15,
                    }}
                  >
                    <Icon
                      color={colors[item.tone]}
                      size={21}
                    />
                    <strong>{item.title}</strong>
                  </div>

                  <div
                    style={{
                      color: colors[item.tone],
                      fontWeight: 800,
                      fontSize: 17,
                    }}
                  >
                    {item.status}
                  </div>

                  <p>{item.detail}</p>
                </article>
              );
            })}
          </div>

          <div className="diagnosis-block">
            <strong>
              What the stability watch observed
            </strong>

            <p style={{ color: '#eaf1ff' }}>
              {result.stability.status}
            </p>

            <p>{result.stability.detail}</p>
          </div>

          <p className="disclaimer">
            This page never starts a new test.
            Results can be affected by Wi-Fi, VPN routing,
            other devices, congestion and which server an app uses.
            Gaming servers, websites, streams and video-call
            platforms were not tested directly.
          </p>

          <p className="disclaimer">
            Bandwidth references: Netflix recommendations and
            Zoom HD video guidance. Both publish requirements
            for specific formats; real-world performance varies.
          </p>
        </>
      )}
    </section>
  );
}
