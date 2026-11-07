import { useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Search,
  ShieldCheck,
} from 'lucide-react';
import {
  FeedbackButton,
  beginTask,
} from './feedback.jsx';

const STATUS = {
  confirmed: {
    label: 'Observed',
    color: '#70e0c6',
    Icon: CheckCircle2,
  },
  mixed: {
    label: 'Mixed evidence',
    color: '#f1c67a',
    Icon: AlertTriangle,
  },
  attention: {
    label: 'Needs attention',
    color: '#f1c67a',
    Icon: AlertTriangle,
  },
  inconclusive: {
    label: 'Inconclusive',
    color: '#90c8f4',
    Icon: HelpCircle,
  },
  not_tested: {
    label: 'Not measured',
    color: '#9aaec7',
    Icon: HelpCircle,
  },
};

const INPUT_STYLE = {
  flex: '1 1 280px',
  minWidth: 0,
  padding: 13,
  borderRadius: 10,
  background: '#0b1528',
  color: '#eef4ff',
  border: '1px solid #37506e',
};

function ResultStep({ step, number }) {
  const tone = STATUS[step.status] || STATUS.inconclusive;
  const Icon = tone.Icon;

  return (
    <article
      className="diagnosis-block"
      style={{
        margin: 0,
        borderLeft: `4px solid ${tone.color}`,
        padding: '18px 20px',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 10,
        }}
      >
        <span
          style={{
            color: '#a9bdd5',
            fontWeight: 700,
          }}
        >
          {number}.
        </span>

        <Icon
          size={20}
          color={tone.color}
          aria-hidden="true"
        />

        <strong style={{ fontSize: 16 }}>
          {step.title}
        </strong>

        <span
          style={{
            color: tone.color,
            fontSize: 12,
            fontWeight: 700,
          }}
        >
          {tone.label}
        </span>
      </div>

      <p>{step.evidence}</p>

      <p style={{ color: '#c4f4e8' }}>
        <strong>Next step:</strong>{' '}
        {step.next_step}
      </p>
    </article>
  );
}

function WebsiteTimings({ website }) {
  if (!website) return null;

  const measurements = [
    ['DNS lookup', website.dns_ms],
    ['TCP connection', website.tcp_ms],
    ['TLS handshake', website.tls_ms],
    ['HTTP first response', website.response_ms],
  ];

  return (
    <details
      style={{
        marginTop: 16,
        color: '#b4c7df',
      }}
    >
      <summary
        style={{
          cursor: 'pointer',
          fontWeight: 700,
        }}
      >
        Detailed website measurements
      </summary>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns:
            'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 10,
          marginTop: 14,
        }}
      >
        {measurements.map(([label, value]) => (
          <div
            key={label}
            className="diagnosis-block"
            style={{ margin: 0 }}
          >
            <p
              style={{
                fontSize: 12,
                marginTop: 0,
              }}
            >
              {label}
            </p>

            <strong style={{ fontSize: 18 }}>
              {typeof value === 'number' &&
              Number.isFinite(value)
                ? `${value.toFixed(1)} ms`
                : 'Not measured'}
            </strong>
          </div>
        ))}
      </div>

      <p style={{ marginTop: 12 }}>
        HTTP status: {website.http_status ?? 'Unavailable'}
        {' · '}
        Address family:{' '}
        {website.address_family ?? 'Not determined'}
      </p>

      <p style={{ overflowWrap: 'anywhere' }}>
        Destination: {website.target ?? 'Not reported'}
      </p>
    </details>
  );
}

export default function GuidedTroubleshootingPanel() {
  const [target, setTarget] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [report, setReport] = useState(null);
  const running = useRef(false);

  async function start(event) {
    event?.preventDefault();

    if (running.current) return;

    const api = window.pywebview?.api;

    if (!api?.run_guided_troubleshooting) {
      setError(
        'Guided troubleshooting requires the updated Windows application.'
      );
      return;
    }

    const explanation = target.trim()
      ? (
          'NetDoctor will check your local network, perform public ' +
          'DNS and connectivity probes, and send one HTTPS HEAD ' +
          'request to the website you entered. No file is downloaded. ' +
          'Remote services can see your public exit IP. Continue?'
        )
      : (
          'NetDoctor will check your local network and perform ' +
          'short DNS, public connectivity and ICMP probes. ' +
          'No large downloads or network setting changes. Continue?'
        );

    if (!window.confirm(explanation)) {
      return;
    }

    running.current = true;
    setBusy(true);
    setError('');
    setReport(null);

    const finish = beginTask(
      'Running guided troubleshooting…',
      'Checking local routing, DNS and public connectivity.'
    );

    try {
      const answer =
        await api.run_guided_troubleshooting(
          target.trim()
        );

      if (!answer?.ok || !answer.report) {
        const message =
          answer?.error ||
          'The guided check could not be completed.';

        setError(message);

        finish(
          'warning',
          'Guided check incomplete',
          message
        );

        return;
      }

      setReport(answer.report);

      finish(
        'success',
        'Guided check complete',
        'The network observations have been reviewed.'
      );
    } catch {
      setError(
        'Guided troubleshooting could not finish. Try again.'
      );

      finish(
        'error',
        'Guided check failed',
        'Please retry on your current connection.'
      );
    } finally {
      running.current = false;
      setBusy(false);
    }
  }

  return (
    <section
      className="panel details-panel"
      style={{
        maxWidth: 1080,
        marginBottom: 22,
      }}
      aria-busy={busy}
    >
      <p className="eyebrow">
        GUIDED NETWORK TROUBLESHOOTING
      </p>

      <h2>Find out where the problem might be</h2>

      <p>
        NetDoctor checks your local connection, DNS and
        internet access together, then explains the
        evidence and what to try next.
      </p>

      <form
        onSubmit={start}
        style={{ marginTop: 20 }}
      >
        <label
          htmlFor="guided-target"
          style={{
            display: 'block',
            fontSize: 13,
            marginBottom: 9,
          }}
        >
          Specific website to investigate (optional)
        </label>

        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <input
            id="guided-target"
            type="text"
            autoComplete="url"
            spellCheck={false}
            placeholder="github.com"
            maxLength={512}
            value={target}
            disabled={busy}
            onChange={event => {
              setTarget(event.target.value);
              setReport(null);
              setError('');
            }}
            style={INPUT_STYLE}
          />

          <FeedbackButton
            className="primary"
            type="submit"
            busy={busy}
          >
            <Search size={17} />
            {busy
              ? 'Checking connection…'
              : 'Start guided check'}
          </FeedbackButton>
        </div>
      </form>

      <p
        className="disclaimer"
        style={{ marginTop: 14 }}
      >
        <ShieldCheck
          size={15}
          style={{
            verticalAlign: 'middle',
            marginRight: 7,
          }}
        />
        Tests start only when requested. The optional
        website check permits public HTTPS destinations
        only. NetDoctor does not change network settings.
      </p>

      {busy && (
        <p
          role="status"
          style={{ color: '#85dace' }}
        >
          Gathering fresh observations. The DNS and
          responsiveness checks may take several seconds.
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
          style={{ marginTop: 24 }}
        >
          <div
            className="diagnosis-block action"
            style={{ marginBottom: 18 }}
          >
            <p className="eyebrow">
              GUIDED RESULT
            </p>

            <h3 style={{ marginTop: 8 }}>
              {report.headline}
            </h3>

            <p>{report.summary}</p>

            <p style={{ color: '#c4f4e8' }}>
              <strong>Recommended action:</strong>{' '}
              {report.next_step}
            </p>
          </div>

          <div
            style={{
              display: 'grid',
              gap: 13,
            }}
          >
            {(report.steps ?? []).map((step, index) => (
              <ResultStep
                key={step.key}
                step={step}
                number={index + 1}
              />
            ))}
          </div>

          <WebsiteTimings website={report.website} />

          <p
            className="disclaimer"
            style={{ marginTop: 17 }}
          >
            {report.limitation}
          </p>

          <p className="disclaimer">
            Checked:{' '}
            {new Date(report.tested_at).toLocaleString()}
          </p>
        </div>
      )}
    </section>
  );
}