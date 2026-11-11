
import { useEffect, useRef, useState } from 'react';
import {
  Activity,
  ArrowLeft,
  CheckCircle2,
  CircleHelp,
  RefreshCw,
  ShieldCheck,
  Wifi,
} from 'lucide-react';

import { confirmInPage } from '../../confirmInPage.mjs';

import {
  assessInternetFault,
} from './internetFault.mjs';

const CHOICES = [
  ['unknown', 'Not tested'],
  ['works', 'Works'],
  ['fails', 'Also has a problem'],
];

function AnswerChoices({
  title,
  help,
  value,
  onChange,
}) {
  return (
    <div style={{ marginTop: 18 }}>
      <strong>{title}</strong>
      <p>{help}</p>

      <div
        className="guided-buttons"
        role="group"
        aria-label={title}
      >
        {CHOICES.map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={
              value === id
                ? 'guided-primary'
                : 'guided-secondary'
            }
            aria-pressed={value === id}
            onClick={() => onChange(id)}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function InternetFaultFlow({ onBack }) {
  const [report, setReport] = useState(null);
  const [otherDevice, setOtherDevice] = useState('unknown');
  const [otherNetwork, setOtherNetwork] = useState('unknown');
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

  async function runDiagnosis() {
    if (running.current) return;

    const api = window.pywebview?.api;

    if (
      typeof api?.run_guided_troubleshooting !== 'function'
    ) {
      setError(
        'Open the NetDoctor Windows application ' +
        'to run this diagnosis.'
      );
      return;
    }

    running.current = true;
    setBusy(true);
    setError('');

    try {
      const approved = await confirmInPage({
        title: 'Run network diagnosis?',
        message:
          'NetDoctor will inspect the current Windows network ' +
          'connection and make short DNS, TCP and ping checks ' +
          'to public test destinations.\n\n' +
          'Those destinations can observe your public IP. ' +
          'No large files will be downloaded, and no network ' +
          'settings will be changed.',
        confirmLabel: 'Run diagnosis',
      });

      if (!approved || !mounted.current) {
        return;
      }

      setReport(null);
      setOtherDevice('unknown');
      setOtherNetwork('unknown');

      const response =
        await api.run_guided_troubleshooting('');

      if (!mounted.current) return;

      if (
        !response?.ok ||
        !Array.isArray(response.report?.steps)
      ) {
        setError(
          response?.error ||
          'The diagnosis did not return usable checks.'
        );
      } else {
        try {
          assessInternetFault(response.report);
          setReport(response.report);
        } catch {
          setError(
            'The diagnosis results were incomplete. ' +
            'Please run the check again.'
          );
        }
      }
    } catch (cause) {
      if (mounted.current) {
        setError(
          cause instanceof Error &&
          cause.message.includes('WebView2')
            ? cause.message
            : 'NetDoctor could not complete the diagnosis. Try again.'
        );
      }
    } finally {
      running.current = false;

      if (mounted.current) {
        setBusy(false);
      }
    }
  }

  const result = report
    ? assessInternetFault(report, {
        otherDevice,
        otherNetwork,
      })
    : null;

  const checkedAt =
    result?.testedAt &&
    Number.isFinite(Date.parse(result.testedAt))
      ? new Date(result.testedAt).toLocaleString()
      : null;

  return (
    <main className="guided-main">
      <header className="guided-header">
        <div>
          <p className="guided-eyebrow">
            CONNECTION FAULT ISOLATION
          </p>

          <h1>What's wrong with my internet?</h1>

          <p>
            Check the connection and identify which part
            needs attention—without guessing whether
            it's the PC, router or ISP.
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
        aria-label="Internet fault diagnosis"
        aria-busy={busy}
      >
        <div className="guided-message">
          <span className="guided-avatar">
            <Activity size={18} />
          </span>

          <div className="guided-bubble">
            <strong>
              Let's check the connection you're using now.
            </strong>

            <p>
              NetDoctor checks the Windows network route,
              gateway responses, DNS and public HTTPS
              connectivity. It compares actual results
              rather than assuming every outage is an
              ISP problem.
            </p>

            <p>
              Run the check while you're experiencing the
              problem, on the connection you want to diagnose.
            </p>

            <div className="guided-buttons">
              <button
                type="button"
                className="guided-primary"
                onClick={runDiagnosis}
                disabled={busy}
              >
                {report
                  ? <RefreshCw size={16} />
                  : <Wifi size={16} />
                }

                {busy
                  ? 'Checking connection…'
                  : report
                    ? 'Run diagnosis again'
                    : 'Diagnose my connection'}
              </button>
            </div>

            {busy && (
              <p role="status">
                A confirmation or network check
                is in progress.
              </p>
            )}

            {error && (
              <p
                className="guided-error"
                role="alert"
              >
                {error}
              </p>
            )}
          </div>
        </div>

        {result && (
          <>
            <div className="guided-message">
              <span className="guided-avatar">
                <CircleHelp size={18} />
              </span>

              <div className="guided-bubble">
                <strong>
                  Two optional comparisons can narrow the cause.
                </strong>

                <p>
                  Only answer what you've actually tried.
                  These answers come from you; NetDoctor
                  can't independently test another device
                  or an ISP's infrastructure.
                </p>

                <AnswerChoices
                  title={
                    'Does another device work on the same ' +
                    'Wi-Fi or router?'
                  }
                  help={
                    'For example, test a website on your ' +
                    'phone with mobile data switched off.'
                  }
                  value={otherDevice}
                  onChange={setOtherDevice}
                />

                <AnswerChoices
                  title={
                    'Does this same PC work through another ' +
                    'internet connection?'
                  }
                  help={
                    'For example, a phone hotspot. Compare ' +
                    'the same website, then return to the ' +
                    'original network before rerunning NetDoctor.'
                  }
                  value={otherNetwork}
                  onChange={setOtherNetwork}
                />
              </div>
            </div>

            <div className="guided-message">
              <span className="guided-avatar">
                <CheckCircle2 size={18} />
              </span>

              <div
                className="guided-bubble"
                aria-live="polite"
              >
                <p className="guided-eyebrow">
                  FINDING
                </p>

                <strong className="guided-answer-title">
                  {result.headline}
                </strong>

                <p>{result.interpretation}</p>

                <div className="guided-next-step">
                  <strong>What to do next</strong>

                  <ol
                    style={{
                      paddingLeft: 21,
                      marginBottom: 0,
                    }}
                  >
                    {result.actions.map((action, index) => (
                      <li
                        key={index}
                        style={{ marginTop: 10 }}
                      >
                        {action}
                      </li>
                    ))}
                  </ol>
                </div>

                <details className="guided-details">
                  <summary>
                    Show checks and evidence
                  </summary>

                  {result.evidence.map(item => (
                    <div
                      key={item.key}
                      style={{ marginTop: 13 }}
                    >
                      <strong>
                        {item.label} · {item.status}
                      </strong>

                      <p>{item.detail}</p>
                    </div>
                  ))}

                  {checkedAt && (
                    <p>Checked: {checkedAt}</p>
                  )}

                  {typeof report.limitation === 'string' && (
                    <p>{report.limitation}</p>
                  )}
                </details>

                <p className="guided-caution">
                  {result.comparisonNote}
                </p>

                <p className="guided-caution">
                  {result.limitation}
                </p>
              </div>
            </div>
          </>
        )}
      </section>

      <footer className="guided-footer">
        <ShieldCheck size={16} />
        Tests run only with your approval.
        No automatic repairs or settings changes.
      </footer>
    </main>
  );
}
