import { confirmInPage } from '../../confirmInPage.mjs';

import { useEffect, useRef, useState } from 'react';
import {
  Activity,
  ArrowLeft,
  Globe2,
  ShieldCheck,
} from 'lucide-react';

import { interpretWebsite } from './websiteDiagnosis.mjs';

const OPTIONS = [
  ['unknown', "Haven't checked"],
  ['works', 'Yes, it opens'],
  ['fails', 'No, it also fails'],
];

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

export default function WebsiteFlow({ onBack }) {
  const [target, setTarget] = useState('');
  const [otherDevice, setOtherDevice] = useState('unknown');
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const running = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;

    return () => {
      mounted.current = false;
    };
  }, []);

  async function check(event) {
    event.preventDefault();

    const website = target.trim();

    if (running.current || !website || website.length > 512) {
      return;
    }

    const api = window.pywebview?.api;

    if (!api?.run_guided_troubleshooting) {
      setError(
        'Open NetDoctor in its Windows desktop window to run this check.'
      );
      return;
    }

    if (!(await confirmInPage({ title: 'Check website connectivity?', message: ('NetDoctor will check your network and contact public test services, ' +
      'then send one HTTPS HEAD request to this website. The external ' +
      'services can see your public IP. It will not download a page, ' +
      'follow redirects or change settings. Continue?').replace(/\s+(?:Continue\?|Start monitoring\?)$/, ''), confirmLabel: 'Check website' }))) {
      return;
    }

    running.current = true;
    setBusy(true);
    setError('');
    setReport(null);

    try {
      const response =
        await api.run_guided_troubleshooting(website);

      if (!mounted.current) return;

      if (response?.ok && response.report?.website) {
        setReport(response.report);
      } else {
        setError(
          response?.error || 'The website check could not finish.'
        );
      }
    } catch {
      if (mounted.current) {
        setError(
          'The website check could not finish. Try again.'
        );
      }
    } finally {
      running.current = false;

      if (mounted.current) {
        setBusy(false);
      }
    }
  }

  const answer = report
    ? interpretWebsite(report, otherDevice)
    : null;

  return (
    <main className="guided-main">
      <header className="guided-header">
        <div>
          <p className="guided-eyebrow">
            GUIDED WEBSITE CHECK
          </p>

          <h1>Why won't a website open?</h1>

          <p>
            Check the website's response and what it proves.
          </p>
        </div>

        <button
          type="button"
          className="guided-restart"
          disabled={busy}
          onClick={onBack}
        >
          <ArrowLeft size={16} />
          All questions
        </button>
      </header>

      <section
        className="guided-chat"
        aria-label="Website troubleshooting"
        aria-busy={busy}
      >
        <Bubble mine>
          Why won't a website open?
        </Bubble>

        <Bubble>
          <strong>
            Which website is giving you trouble?
          </strong>

          <p>
            Enter its domain or an HTTPS address.
            Local router pages and HTTP-only websites
            aren't supported by this check.
          </p>

          <form
            className="guided-wan-form"
            onSubmit={check}
          >
            <label htmlFor="website-to-check">
              Website address
            </label>

            <input
              id="website-to-check"
              type="text"
              autoComplete="url"
              spellCheck={false}
              maxLength={512}
              placeholder="github.com"
              value={target}
              disabled={busy}
              onChange={event => {
                setTarget(event.target.value);
                setOtherDevice('unknown');
                setReport(null);
                setError('');
              }}
            />

            <div className="guided-buttons">
              <button
                className="guided-primary"
                type="submit"
                disabled={busy || !target.trim()}
              >
                <Globe2 size={16} />
                {busy
                  ? 'Checking website…'
                  : 'Check website'}
              </button>
            </div>
          </form>

          <p className="guided-caution">
            A short on-demand check; no file download
            or settings changes.
          </p>

          {busy && (
            <p role="status">
              Checking basic internet access and
              the selected website…
            </p>
          )}

          {error && (
            <p className="guided-error" role="alert">
              {error}
            </p>
          )}
        </Bubble>

        {answer && (
          <Bubble>
            <strong className="guided-answer-title">
              {answer.headline}
            </strong>

            <p>{answer.finding}</p>

            <p>
              <strong>Other internet checks:</strong>{' '}
              {answer.generalFinding}
            </p>

            <div style={{ marginTop: 17 }}>
              <strong>
                Does the same website open on another device
                using the same Wi-Fi?
              </strong>

              <div className="guided-buttons">
                {OPTIONS.map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    className="guided-secondary"
                    aria-pressed={otherDevice === id}
                    onClick={() => setOtherDevice(id)}
                  >
                    {otherDevice === id ? '✓ ' : ''}
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div
              className="guided-next-step"
              aria-live="polite"
            >
              <strong>What to do next</strong>
              <p>{answer.next}</p>
            </div>

            <details className="guided-details">
              <summary>Technical evidence</summary>

              <p>
                <strong>Tested address:</strong>{' '}
                {answer.details.target || 'Not reported'}
              </p>

              <p>
                <strong>HTTP status:</strong>{' '}
                {answer.details.httpStatus ?? 'Not received'}
              </p>

              <p>
                <strong>Last completed stage:</strong>{' '}
                {answer.details.stage}
              </p>

              <p>
                <strong>IP version:</strong>{' '}
                {answer.details.addressFamily || 'Not determined'}
              </p>

              <p>{answer.limitation}</p>
            </details>
          </Bubble>
        )}
      </section>

      <footer className="guided-footer">
        <ShieldCheck size={16} />
        Only checks you request are performed.
      </footer>
    </main>
  );
}
