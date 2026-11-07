
import { useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Globe2,
  Search,
  ShieldCheck,
} from 'lucide-react';
import {
  FeedbackButton,
  beginTask,
} from './feedback.jsx';

const inputStyle = {
  flex: '1 1 290px',
  minWidth: 0,
  padding: 13,
  borderRadius: 10,
  background: '#0b1528',
  color: '#eef4ff',
  border: '1px solid #37506e',
};

function Metric({ title, value }) {
  return (
    <article
      className="mini-metric"
      style={{ minWidth: 0 }}
    >
      <Globe2 size={17} />
      <span>{title}</span>
      <strong
        style={{
          fontSize: 18,
          overflowWrap: 'anywhere',
        }}
      >
        {typeof value === 'number' && Number.isFinite(value)
          ? `${value.toFixed(1)} ms`
          : 'Not measured'}
      </strong>
    </article>
  );
}

export default function WebsiteDiagnosticsPanel() {
  const [target, setTarget] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [report, setReport] = useState(null);
  const running = useRef(false);

  async function check(event) {
    event?.preventDefault();

    if (running.current || !target.trim()) return;

    const api = window.pywebview?.api;

    if (!api?.check_website) {
      setError(
        'Website checks require the updated Windows desktop application.'
      );
      return;
    }

    if (!window.confirm(
      'NetDoctor will look up this hostname and make one direct HTTPS ' +
      'HEAD request to the selected public website. The destination ' +
      'can see your public exit IP. No file body will be downloaded, ' +
      'redirects will not be followed, and proxy settings may differ ' +
      'from your browser. Continue?'
    )) {
      return;
    }

    running.current = true;
    setBusy(true);
    setError('');
    setReport(null);

    const finish = beginTask(
      'Checking website response…',
      'Measuring DNS, TCP, TLS and the HTTPS response.'
    );

    try {
      const answer = await api.check_website(
        target.trim()
      );

      if (!answer?.ok || !answer.report) {
        const message =
          answer?.error ||
          'The website check could not be completed.';

        setError(message);

        finish(
          'warning',
          'Website check incomplete',
          message
        );

        return;
      }

      setReport(answer.report);

      const clearSuccess =
        answer.report.status === 'responded' &&
        (answer.report.http_status ?? 599) < 400;

      finish(
        clearSuccess ? 'success' : 'warning',
        'Website check finished',
        answer.report.headline
      );
    } catch {
      setError(
        'The website check could not finish. Try again.'
      );

      finish(
        'error',
        'Website check failed',
        'Try again on your current connection.'
      );
    } finally {
      running.current = false;
      setBusy(false);
    }
  }

  const healthy =
    report?.status === 'responded' &&
    (report.http_status ?? 599) < 400;

  return (
    <section
      className="panel details-panel"
      style={{
        maxWidth: 1080,
        marginTop: 22,
      }}
      aria-busy={busy}
    >
      <p className="eyebrow">
        OPTIONAL DESTINATION TEST
      </p>

      <h2>Why is a website responding slowly?</h2>

      <p>
        Check one public HTTPS website. NetDoctor measures
        how long name lookup, connection setup, secure
        negotiation and the first HTTP response take.
      </p>

      <form
        onSubmit={check}
        style={{ marginTop: 20 }}
      >
        <label
          htmlFor="website-target"
          style={{
            display: 'block',
            fontSize: 13,
            marginBottom: 9,
          }}
        >
          Website domain or HTTPS URL
        </label>

        <div
          style={{
            display: 'flex',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <input
            id="website-target"
            type="text"
            autoComplete="url"
            spellCheck={false}
            placeholder="github.com"
            maxLength={512}
            style={inputStyle}
            value={target}
            disabled={busy}
            onChange={event => {
              setTarget(event.target.value);
              setReport(null);
              setError('');
            }}
          />

          <FeedbackButton
            className="primary"
            type="submit"
            busy={busy}
            disabled={!target.trim()}
          >
            <Search size={17} />
            {busy
              ? 'Checking website…'
              : 'Check website'}
          </FeedbackButton>
        </div>
      </form>

      <p
        className="disclaimer"
        style={{ marginTop: 13 }}
      >
        <ShieldCheck
          size={15}
          style={{
            verticalAlign: 'middle',
            marginRight: 7,
          }}
        />
        Public HTTPS port 443 only. No login, downloads,
        redirects or local-network targets. No automatic tests.
      </p>

      {busy && (
        <p
          role="status"
          style={{ color: '#85dace' }}
        >
          Measuring this destination…
        </p>
      )}

      {error && (
        <p
          className="inline-warning"
          role="alert"
        >
          {error}
        </p>
      )}

      {report && (
        <div
          aria-live="polite"
          style={{ marginTop: 20 }}
        >
          <div
            className="diagnosis-block"
            style={{
              borderLeft: `4px solid ${
                healthy ? '#63e8cb' : '#f1c67a'
              }`,
            }}
          >
            <div
              style={{
                display: 'flex',
                gap: 10,
                alignItems: 'center',
              }}
            >
              {healthy ? (
                <CheckCircle2
                  color="#63e8cb"
                  size={22}
                />
              ) : (
                <AlertTriangle
                  color="#f1c67a"
                  size={22}
                />
              )}

              <strong style={{ fontSize: 17 }}>
                {report.headline}
              </strong>
            </div>

            <p style={{ overflowWrap: 'anywhere' }}>
              {report.target}
            </p>

            <p>{report.explanation}</p>

            <p>
              <strong>HTTP status:</strong>{' '}
              {report.http_status ?? 'Not received'}
              {' · '}
              <strong>Address family:</strong>{' '}
              {report.address_family ??
                'Not determined'}
            </p>
          </div>

          <div
            className="metric-row"
            style={{
              marginTop: 17,
              gridTemplateColumns:
                'repeat(2, minmax(0, 1fr))',
            }}
          >
            <Metric
              title="DNS LOOKUP"
              value={report.dns_ms}
            />

            <Metric
              title="TCP CONNECT"
              value={report.tcp_ms}
            />

            <Metric
              title="TLS HANDSHAKE"
              value={report.tls_ms}
            />

            <Metric
              title="HTTP FIRST RESPONSE"
              value={report.response_ms}
            />
          </div>

          <div
            className="diagnosis-block action"
            style={{ marginTop: 18 }}
          >
            <strong>
              What to try next
            </strong>

            <p>{report.next_step}</p>
          </div>

          <p className="disclaimer">
            {report.limitation}
          </p>

          <p className="disclaimer">
            Checked{' '}
            {new Date(report.tested_at).toLocaleString()}
            {' · '}
            Stage: {report.stage}
          </p>
        </div>
      )}
    </section>
  );
}
