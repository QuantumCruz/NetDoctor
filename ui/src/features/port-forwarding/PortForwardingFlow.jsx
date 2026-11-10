
import { useRef, useState } from 'react';
import { Activity, ArrowRight, CircleHelp, RotateCcw, ShieldCheck } from 'lucide-react';
import { classifyWan } from './portForwarding.mjs';
import PortForwardingResult from './PortForwardingResult.jsx';

const QUESTION = 'Why is my port forwarding not working?';

function Bubble({ mine = false, children }) {
  return (
    <div className={`guided-message ${mine ? 'guided-mine' : ''}`}>
      {!mine && <span className="guided-avatar"><Activity size={18} /></span>}
      <div className="guided-bubble">{children}</div>
    </div>
  );
}

/** One guided question. New questions should be added only after this works. */
export default function PortForwardingFlow({ onExploreTools }) {
  const [step, setStep] = useState('start');
  const [wan, setWan] = useState('');
  const [help, setHelp] = useState(false);
  const [connection, setConnection] = useState('unknown');
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const running = useRef(false);

  const wanInfo = classifyWan(wan);

  function restart() {
    if (running.current) return;
    setStep('start');
    setWan('');
    setHelp(false);
    setConnection('unknown');
    setReport(null);
    setError('');
  }

  async function compare() {
    if (running.current || !wanInfo) return;
    const api = window.pywebview?.api;
    if (!api?.check_public_connection) {
      setError('Public IP lookup requires the NetDoctor Windows app. The WAN address classification remains valid.');
      return;
    }

    running.current = true;
    setBusy(true);
    setError('');

    try {
      const response = await api.check_public_connection(wan.trim());
      if (!response?.ok || !response.report) {
        setError(response?.error || 'The public IP lookup could not finish.');
      } else {
        setReport(response.report);
      }
    } catch {
      setError('The public IP lookup could not finish. Try again.');
    } finally {
      running.current = false;
      setBusy(false);
    }
  }

  return (
    <main className="guided-main">
      <header className="guided-header">
        <div>
          <p className="guided-eyebrow">NETWORK HELP, MADE SIMPLE</p>
          <h1>Ask NetDoctor</h1>
          <p>Choose a question and get a straightforward explanation.</p>
        </div>
        {step !== 'start' && (
          <button type="button" className="guided-restart" disabled={busy} onClick={restart}>
            <RotateCcw size={16} /> Start over
          </button>
        )}
      </header>

      <section className="guided-chat" aria-label="Troubleshooting conversation" aria-busy={busy}>
        <Bubble>
          <strong>Hello! I'm NetDoctor.</strong>
          <p>What can I help you understand about your network?</p>
        </Bubble>

        {step === 'start' && (
          <button type="button" className="guided-question" onClick={() => setStep('input')}>
            <CircleHelp size={19} /> <span>{QUESTION}</span> <ArrowRight size={18} />
          </button>
        )}
        {step !== 'start' && <Bubble mine>{QUESTION}</Bubble>}

        {step === 'input' && (
          <Bubble>
            <strong>What is your router's WAN IPv4 address?</strong>
            <p>Find this in your router settings. It is different from your computer's local address.</p>
            <form
              className="guided-wan-form"
              onSubmit={event => { event.preventDefault(); if (wanInfo) setStep('result'); }}
            >
              <label htmlFor="guided-wan">Router WAN IPv4</label>
              <input
                id="guided-wan"
                autoComplete="off"
                spellCheck={false}
                maxLength={45}
                value={wan}
                onChange={event => { setWan(event.target.value); setReport(null); }}
                placeholder="Enter the address from your router"
              />
              {wan.trim() && !wanInfo && <small className="guided-error">Enter a valid IPv4 address.</small>}
              <div className="guided-buttons">
                <button type="submit" className="guided-primary" disabled={!wanInfo}>
                  Check address <ArrowRight size={16} />
                </button>
                <button type="button" className="guided-secondary" onClick={() => setHelp(!help)}>
                  {help ? 'Hide instructions' : 'Where do I find it?'}
                </button>
              </div>
            </form>
            {help && (
              <p className="guided-help">
                Open your router settings and look for <strong>Internet</strong>,
                <strong> WAN</strong>, or <strong>Connection Status</strong>.
                Copy the WAN IPv4 shown there.
              </p>
            )}
          </Bubble>
        )}

        {step === 'result' && wanInfo && (
          <>
            <Bubble mine>My router WAN IPv4 is {wan.trim()}.</Bubble>
            <Bubble>
              <PortForwardingResult
                wan={wan}
                wanInfo={wanInfo}
                connection={connection}
                setConnection={setConnection}
                report={report}
                busy={busy}
                error={error}
                onCompare={compare}
                onRestart={restart}
                onExploreTools={onExploreTools}
              />
            </Bubble>
          </>
        )}
      </section>

      <footer className="guided-footer">
        <ShieldCheck size={16} /> Confirmed findings are separated from checks not yet run.
      </footer>
    </main>
  );
}
