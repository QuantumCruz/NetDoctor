import { confirmInPage } from '../../confirmInPage.mjs';

import { useRef, useState } from 'react';
import {
  Activity,
  ArrowLeft,
  RotateCcw,
  ShieldCheck,
  Wifi,
} from 'lucide-react';

import { compareVpnExit } from './vpnDiagnosis.mjs';

function Bubble({ children, mine = false }) {
  return (
    <div
      className={`guided-message ${
        mine ? 'guided-mine' : ''
      }`}
    >
      {!mine && (
        <span className="guided-avatar">
          <Activity size={18} />
        </span>
      )}

      <div className="guided-bubble">
        {children}
      </div>
    </div>
  );
}

function Observation({ label, report }) {
  return (
    <div style={{ marginTop: 14 }}>
      <strong>{label}</strong>

      <p>
        Public IP: {report.public_ip}
        {' ('}{report.ip_family}{')'}
      </p>

      <p>
        Approximate country:{' '}
        {report.country || 'Not identified'}
      </p>

      {report.city && (
        <p>
          Approximate city: {report.city}
        </p>
      )}

      <p>
        Exit network:{' '}
        {report.exit_network || 'Not identified'}
      </p>
    </div>
  );
}

export default function VpnCheckFlow({ onBack }) {
  const [before, setBefore] = useState(null);
  const [after, setAfter] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const running = useRef(false);

  function restart() {
    if (running.current) return;

    setBefore(null);
    setAfter(null);
    setError('');
  }

  async function lookup(stage) {
    if (running.current) return;

    const api = window.pywebview?.api;

    if (!api?.check_public_connection) {
      setError(
        'Open NetDoctor in the Windows desktop application ' +
        'to check your public IP.'
      );
      return;
    }

    const prompt = stage === 'before'
      ? (
          'Disconnect your VPN before the first check. ' +
          'NetDoctor will contact IP.SB over HTTPS to read ' +
          'your public IP and approximate country. ' +
          'IP.SB can see your public IP. Continue?'
        )
      : (
          'Connect your VPN now. NetDoctor will contact ' +
          'IP.SB again over HTTPS to compare the observed ' +
          'exit IP and approximate country. IP.SB can see ' +
          'your public IP. Continue?'
        );

    if (!(await confirmInPage({ title: 'Check VPN exit location?', message: (prompt).replace(/\s+(?:Continue\?|Start monitoring\?)$/, ''), confirmLabel: 'Check public IP' }))) return;

    running.current = true;
    setBusy(true);
    setError('');

    try {
      const response =
        await api.check_public_connection('');

      if (!response?.ok || !response.report) {
        setError(
          response?.error ||
          'The public-IP lookup failed.'
        );
      } else if (
        !response.report.public_ip ||
        !response.report.ip_family
      ) {
        setError(
          'The lookup returned incomplete ' +
          'public-IP information.'
        );
      } else if (stage === 'before') {
        setBefore(response.report);
        setAfter(null);
      } else {
        setAfter(response.report);
      }
    } catch {
      setError(
        'The public-IP lookup could not finish. Try again.'
      );
    } finally {
      running.current = false;
      setBusy(false);
    }
  }

  const result = before && after
    ? compareVpnExit(before, after)
    : null;

  return (
    <main className="guided-main">
      <header className="guided-header">
        <div>
          <p className="guided-eyebrow">
            VPN EXIT VERIFICATION
          </p>

          <h1>Is my VPN working?</h1>

          <p>
            See whether your public IP and apparent
            country change.
          </p>
        </div>

        <div
          className="guided-buttons"
          style={{ marginTop: 0 }}
        >
          <button
            type="button"
            className="guided-restart"
            disabled={busy}
            onClick={onBack}
          >
            <ArrowLeft size={16} />
            All questions
          </button>

          {before && (
            <button
              type="button"
              className="guided-restart"
              disabled={busy}
              onClick={restart}
            >
              <RotateCcw size={16} />
              Start over
            </button>
          )}
        </div>
      </header>

      <section
        className="guided-chat"
        aria-label="VPN public exit check"
        aria-busy={busy}
      >
        <Bubble mine>
          Is my VPN working?
        </Bubble>

        <Bubble>
          <strong>
            First, disconnect your VPN.
          </strong>

          <p>
            NetDoctor will record the public address
            and approximate country seen by one HTTPS
            lookup. It will not change your VPN settings.
          </p>

          {!before && (
            <div className="guided-buttons">
              <button
                type="button"
                className="guided-primary"
                onClick={() => lookup('before')}
                disabled={busy}
              >
                <Wifi size={16} />

                {busy
                  ? 'Checking…'
                  : 'Check with VPN disconnected'}
              </button>
            </div>
          )}

          {error && (
            <p
              className="guided-error"
              role="alert"
            >
              {error}
            </p>
          )}
        </Bubble>

        {before && (
          <Bubble>
            <Observation
              label="First check (VPN disconnected as reported)"
              report={before}
            />

            {!after && (
              <>
                <div className="guided-next-step">
                  <strong>
                    Now connect your VPN.
                  </strong>

                  <p>
                    Choose your VPN server and wait
                    for the VPN app to report connected.
                    Then check again. The app cannot
                    independently confirm which VPN
                    toggle you pressed.
                  </p>
                </div>

                <div className="guided-buttons">
                  <button
                    type="button"
                    className="guided-primary"
                    onClick={() => lookup('after')}
                    disabled={busy}
                  >
                    <ShieldCheck size={16} />

                    {busy
                      ? 'Checking…'
                      : 'VPN connected — check again'}
                  </button>
                </div>
              </>
            )}
          </Bubble>
        )}

        {result && (
          <Bubble>
            <strong className="guided-answer-title">
              {result.headline}
            </strong>

            <p>{result.explanation}</p>
            <p>{result.location}</p>

            <Observation
              label="Second check (VPN connected as reported)"
              report={after}
            />

            <div className="guided-next-step">
              <strong>
                What to do next
              </strong>

              <p>{result.next}</p>
            </div>

            <p className="guided-caution">
              {result.limitation}
            </p>
          </Bubble>
        )}
      </section>

      <footer className="guided-footer">
        <ShieldCheck size={16} />
        Both lookups require your approval.
        No physical-location access.
      </footer>
    </main>
  );
}
