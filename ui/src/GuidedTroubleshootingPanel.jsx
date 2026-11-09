
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
    label: 'Possible issue',
    color: '#f1c67a',
    Icon: AlertTriangle,
  },
  attention: {
    label: 'Needs checking',
    color: '#f1c67a',
    Icon: AlertTriangle,
  },
  inconclusive: {
    label: 'Unknown',
    color: '#90c8f4',
    Icon: HelpCircle,
  },
  not_tested: {
    label: 'Not checked',
    color: '#9aaec7',
    Icon: HelpCircle,
  },
};

const STAGE_LABELS = {
  local: 'Local connection',
  dns: 'Website name lookup',
  internet: 'Internet access',
  website: 'Selected website',
};

const FRIENDLY_HEADLINES = {
  'General HTTPS and the selected website responded':
    'The tested services and website responded',
  'General connectivity works; the selected website needs investigation':
    'The selected website needs a closer look',
  'The selected website responded despite other uncertain checks':
    'The website responded, but some checks were unclear',
  'Connection behavior differs by destination':
    'Some services responded; others did not',
  'Internet reachability remains unverified':
    'Internet access could not be confirmed',
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

function CheckRow({ step }) {
  const tone = STATUS[step.status] || STATUS.inconclusive;
  const Icon = tone.Icon;

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 10,
        padding: '12px 0',
        borderBottom: '1px solid #2b405b',
      }}
    >
      <strong>
        {STAGE_LABELS[step.key] || step.title}
      </strong>

      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 7,
          color: tone.color,
          fontSize: 13,
        }}
      >
        <Icon size={17} aria-hidden="true" />
        {tone.label}
      </span>
    </div>
  );
}

function WebsiteTimings({ website }) {
  if (!website) return null;

  const measurements = [
    ['Website name lookup', website.dns_ms],
    ['Connecting to the website', website.tcp_ms],
    ['Setting up the secure connection', website.tls_ms],
    ['First response from the website', website.response_ms],
  ];

  return (
    <div style={{ marginTop: 18 }}>
      <strong>Website measurements</strong>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns:
            'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 10,
          marginTop: 10,
        }}
      >
        {measurements.map(([label, value]) => (
          <div
            key={label}
            className="diagnosis-block"
            style={{ margin: 0 }}
          >
            <p>{label}</p>

            <strong>
              {typeof value === 'number' &&
              Number.isFinite(value)
                ? `${value.toFixed(1)} ms`
                : 'Not measured'}
            </strong>
          </div>
        ))}
      </div>

      <p>
        HTTP status: {website.http_status ?? 'Not received'}
      </p>

      <p>
        IP version: {website.address_family ?? 'Unknown'}
      </p>

      <p style={{ overflowWrap: 'anywhere' }}>
        Website: {website.target ?? 'Not reported'}
      </p>

      {website.limitation && (
        <p>{website.limitation}</p>
      )}
    </div>
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
        'Open the updated NetDoctor Windows app to run a diagnosis.'
      );
      return;
    }

    const explanation = target.trim()
      ? (
          'NetDoctor will check your connection, contact public test services, ' +
          'and send one small request to the website you entered. ' +
          'Those services can see your public IP address. ' +
          'No file will be downloaded and no settings will be changed. Continue?'
        )
      : (
          'NetDoctor will check your connection and contact public test ' +
          'services. No large files will be downloaded and no settings ' +
          'will be changed. Continue?'
        );

    if (!window.confirm(explanation)) return;

    running.current = true;
    setBusy(true);
    setError('');
    setReport(null);

    const finish = beginTask(
      'Checking your connection…',
      'Collecting a few short measurements.'
    );

    try {
      const answer =
        await api.run_guided_troubleshooting(
          target.trim()
        );

      if (!answer?.ok || !answer.report) {
        const message =
          answer?.error ||
          'The diagnosis could not be completed.';

        setError(message);

        finish(
          'warning',
          'Diagnosis incomplete',
          message
        );

        return;
      }

      setReport(answer.report);

      finish(
        'success',
        'Diagnosis complete',
        'Your results and suggested next step are ready.'
      );
    } catch {
      setError(
        'The diagnosis could not finish. Please try again.'
      );

      finish(
        'error',
        'Diagnosis failed',
        'Please try again.'
      );
    } finally {
      running.current = false;
      setBusy(false);
    }
  }

  return (
    <section
      className="panel details-panel"
      style={{ maxWidth: 1080 }}
      aria-busy={busy}
    >
      <p className="eyebrow">
        NETWORK DIAGNOSIS
      </p>

      <h2>
        Find out what may be affecting your connection
      </h2>

      <p>
        Check your internet connection and get practical
        advice. You can also include a specific website.
      </p>

      <form
        onSubmit={start}
        style={{ marginTop: 20 }}
      >
        <label
          htmlFor="diagnosis-website"
          style={{
            display: 'block',
            fontSize: 13,
            marginBottom: 9,
          }}
        >
          Website to check (optional)
        </label>

        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <input
            id="diagnosis-website"
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
              ? 'Running diagnosis…'
              : 'Run diagnosis'}
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

        Leave the website field empty for a general
        check. Tests run only when you choose.
        No network settings are changed.
      </p>

      {busy && (
        <p
          role="status"
          style={{ color: '#85dace' }}
        >
          Checking your connection.
          This may take several seconds.
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
              RESULT
            </p>

            <h3 style={{ marginTop: 8 }}>
              {FRIENDLY_HEADLINES[report.headline] ||
                report.headline}
            </h3>

            <p>
              These are observations from a short check,
              not proof of what caused a problem.
            </p>

            <strong>
              What to try next
            </strong>

            <p>{report.next_step}</p>
          </div>

          <h3 style={{ marginBottom: 8 }}>
            Checks performed
          </h3>

          <div style={{ marginBottom: 18 }}>
            {(report.steps ?? []).map(step => (
              <CheckRow
                key={step.key}
                step={step}
              />
            ))}
          </div>

          <details
            style={{
              marginTop: 18,
              padding: '13px 16px',
              borderRadius: 10,
              border: '1px solid #2b405b',
              color: '#b4c7df',
            }}
          >
            <summary
              style={{
                cursor: 'pointer',
                fontWeight: 700,
              }}
            >
              Details — measurements and limitations
            </summary>

            <div
              style={{
                paddingTop: 12,
                lineHeight: 1.65,
              }}
            >
              <p>
                <strong>Summary:</strong>{' '}
                {report.summary}
              </p>

              <p>
                <strong>How to read the results:</strong>{' '}
                Observed means a check produced evidence.
                Possible means a problem may need investigating.
                Unknown means the check did not establish a clear
                result.
              </p>

              {(report.steps ?? []).map(step => (
                <div
                  key={step.key}
                  style={{ marginTop: 14 }}
                >
                  <strong>{step.title}</strong>

                  <p>{step.evidence}</p>

                  <p>
                    <strong>Suggested check:</strong>{' '}
                    {step.next_step}
                  </p>
                </div>
              ))}

              <WebsiteTimings
                website={report.website}
              />

              <p>{report.limitation}</p>

              <p>
                Checked:{' '}
                {new Date(
                  report.tested_at
                ).toLocaleString()}
              </p>
            </div>
          </details>
        </div>
      )}
    </section>
  );
}
