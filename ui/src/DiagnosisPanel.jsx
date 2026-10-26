
import { useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Search,
} from 'lucide-react';
import { FeedbackButton, beginTask } from './feedback.jsx';

const COLORS = {
  observed: '#f1c67a',
  possible: '#90c8f4',
  next_check: '#70e0c6',
};

export default function DiagnosisPanel({
  overview,
  reading,
  onRecheck,
  checking = false,
}) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function load({ silent = false } = {}) {
    if (busy && !silent) return;

    const finish = silent
      ? null
      : beginTask(
          'Refreshing diagnosis…',
          'Reviewing saved network measurements.'
        );

    if (!window.pywebview?.api?.get_diagnosis_insights) {
      setMessage(
        'Open the Windows app to see the combined diagnosis.'
      );

      finish?.(
        'warning',
        'Diagnosis not available',
        'Start the Windows desktop app.'
      );
      return;
    }

    setBusy(true);
    setMessage('');

    try {
      const report =
        await window.pywebview.api.get_diagnosis_insights(
          overview,
          reading ?? null
        );

      setData(report);

      finish?.(
        'success',
        'Diagnosis refreshed',
        `${report.findings?.length ?? 0} findings reviewed.`
      );
    } catch {
      setMessage(
        'Could not combine the measurements right now.'
      );

      finish?.(
        'error',
        'Diagnosis refresh failed',
        'Please try again.'
      );
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load({ silent: true });
  }, [overview, reading?.tested_at]);

  return (
    <section
      className="panel details-panel"
      style={{ maxWidth: 1080 }}
      aria-busy={busy}
    >
      <p className="eyebrow">
        EVIDENCE-BASED TROUBLESHOOTING
      </p>

      <div
        className="panel-heading"
        style={{ alignItems: 'flex-start' }}
      >
        <div>
          <h2>
            {data?.headline ??
              'Reviewing connection clues'}
          </h2>

          <p>
            {data?.summary ??
              'Looking at your last checks without starting new tests.'}
          </p>
        </div>

        <FeedbackButton
          className="text-link"
          busy={busy}
          onClick={() => load()}
        >
          <RefreshCw size={16} />
          Refresh insights
        </FeedbackButton>
      </div>

      {message && (
        <p role="alert" className="inline-warning">
          {message}
        </p>
      )}

      {busy && (
        <p role="status">
          Reviewing existing measurements…
        </p>
      )}

      {data && (
        <>
          <div
            style={{
              display: 'grid',
              gap: 13,
              marginTop: 23,
            }}
          >
            {data.findings.map(item => {
              const tone =
                COLORS[item.kind] || COLORS.next_check;

              const Icon =
                item.kind === 'observed'
                  ? AlertTriangle
                  : item.kind === 'possible'
                    ? Search
                    : CheckCircle2;

              return (
                <article
                  key={item.code}
                  className="diagnosis-block"
                  style={{
                    margin: 0,
                    borderLeft: `4px solid ${tone}`,
                    padding: '18px 21px',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      gap: 10,
                      alignItems: 'center',
                      flexWrap: 'wrap',
                    }}
                  >
                    <Icon size={21} color={tone} />

                    <strong style={{ fontSize: 17 }}>
                      {item.title}
                    </strong>

                    <span
                      style={{
                        color: tone,
                        fontSize: 12,
                        fontWeight: 700,
                      }}
                    >
                      {item.kind === 'observed'
                        ? 'Observed clue'
                        : item.kind === 'possible'
                          ? 'Possible contributor'
                          : 'Suggested check'}
                    </span>
                  </div>

                  <p>{item.evidence}</p>

                  <p style={{ color: '#c4f4e8' }}>
                    <strong>Try this:</strong>{' '}
                    {item.next_step}
                  </p>
                </article>
              );
            })}
          </div>

          <div
            className="diagnosis-block action"
            style={{ marginTop: 20 }}
          >
            <strong>
              Recommended next step
            </strong>

            <p>{data.next_step}</p>

            <FeedbackButton
              className="text-link"
              busy={checking}
              disabled={busy}
              onClick={onRecheck}
            >
              <Activity size={16} />
              Run a new quick connection check
            </FeedbackButton>
          </div>

          <details
            style={{
              marginTop: 22,
              color: '#b4c7df',
            }}
          >
            <summary
              style={{
                cursor: 'pointer',
                fontWeight: 700,
              }}
            >
              What we know and what remains uncertain
            </summary>

            <div
              style={{
                padding: '10px 0 0 14px',
                lineHeight: 1.7,
              }}
            >
              {data.notes.map((line, i) => (
                <p key={i}>{line}</p>
              ))}

              <p>
                Recent stability rounds reviewed:{' '}
                {data.history_rounds}
              </p>

              <p>
                Speed reading current:{' '}
                {data.speed_fresh
                  ? 'Within 2 hours'
                  : 'No current reading'}
              </p>

              <p>{data.limitation}</p>
            </div>
          </details>
        </>
      )}
    </section>
  );
}
