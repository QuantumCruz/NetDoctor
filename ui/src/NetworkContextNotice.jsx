import { useEffect, useState } from 'react';
import { AlertTriangle, RefreshCw, X } from 'lucide-react';

export default function NetworkContextNotice() {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  async function refresh() {
    const api = window.pywebview?.api;

    if (!api?.get_network_context_status) return;

    setBusy(true);

    try {
      setStatus(
        await api.get_network_context_status()
      );
    } catch {
      setStatus({
        state: 'unverified',
        message:
          'NetDoctor could not compare the saved speed result ' +
          'with this connection.',
      });
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (window.pywebview?.api) {
      refresh();
    } else {
      window.addEventListener(
        'pywebviewready',
        refresh,
        { once: true }
      );
    }

    window.addEventListener('focus', refresh);

    return () => {
      window.removeEventListener(
        'pywebviewready',
        refresh
      );

      window.removeEventListener(
        'focus',
        refresh
      );
    };
  }, []);

  if (
    dismissed ||
    !['changed', 'unverified'].includes(status?.state)
  ) {
    return null;
  }

  const changed = status.state === 'changed';

  return (
    <aside
      role="status"
      aria-live="polite"
      style={{
        position: 'fixed',
        bottom: 20,
        left: 'clamp(16px, 20vw, 310px)',
        zIndex: 9000,
        width: 'min(420px, calc(100vw - 36px))',
        padding: '16px 18px',
        borderRadius: 14,
        border: `1px solid ${
          changed ? '#b78458' : '#476684'
        }`,
        background: '#15263e',
        boxShadow: '0 14px 36px #0009',
        color: '#eaf1ff',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}
      >
        <AlertTriangle
          size={19}
          color={
            changed ? '#f1c67a' : '#90c8f4'
          }
        />

        <strong style={{ flex: 1 }}>
          {changed
            ? 'Your connection details changed'
            : 'Earlier speed result needs checking'}
        </strong>

        <button
          type="button"
          aria-label="Dismiss network notice"
          onClick={() => setDismissed(true)}
          style={{
            border: 0,
            background: 'transparent',
            color: '#c6d6e8',
            cursor: 'pointer',
          }}
        >
          <X size={18} />
        </button>
      </div>

      <p
        style={{
          margin: '10px 0',
          lineHeight: 1.5,
          fontSize: 13,
          color: '#c5d5e9',
        }}
      >
        {status.message} The speed gauges may show an
        earlier measurement; they are not live values.
      </p>

      <button
        type="button"
        disabled={busy}
        onClick={refresh}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 7,
          padding: 0,
          border: 0,
          background: 'transparent',
          color: '#76e5dc',
          fontWeight: 700,
          cursor: busy ? 'progress' : 'pointer',
        }}
      >
        <RefreshCw size={15} />

        {busy
          ? 'Comparing local network details…'
          : 'Recheck connection details'}
      </button>
    </aside>
  );
}