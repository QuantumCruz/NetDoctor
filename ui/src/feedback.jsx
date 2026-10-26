
import { useEffect, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Info,
  LoaderCircle,
  X,
} from 'lucide-react';
import './feedback.css';

let nextId = 0;
let notices = [];

const listeners = new Set();
const timers = new Map();

function broadcast() {
  listeners.forEach(listener => listener([...notices]));
}

export function dismissNotice(id) {
  if (timers.has(id)) {
    clearTimeout(timers.get(id));
  }

  timers.delete(id);
  notices = notices.filter(item => item.id !== id);
  broadcast();
}

function put(id, kind, title, detail = '') {
  if (timers.has(id)) {
    clearTimeout(timers.get(id));
  }

  timers.delete(id);

  const item = {
    id,
    kind,
    title: String(title),
    detail: String(detail),
  };

  notices = [
    item,
    ...notices.filter(entry => entry.id !== id),
  ].slice(0, 4);

  broadcast();

  if (kind !== 'working') {
    timers.set(
      id,
      setTimeout(() => dismissNotice(id), 5500),
    );
  }

  return id;
}

export function notify(kind, title, detail = '') {
  nextId += 1;
  return put(nextId, kind, title, detail);
}

export function beginTask(title, detail = '') {
  const id = notify('working', title, detail);
  let resolved = false;

  return (kind, finalTitle, finalDetail = '') => {
    if (resolved) return;

    resolved = true;
    put(id, kind, finalTitle, finalDetail);
  };
}

export function FeedbackButton({
  busy = false,
  className = '',
  children,
  disabled,
  ...rest
}) {
  return (
    <button
      {...rest}
      type={rest.type ?? 'button'}
      className={`${className} nd-action ${
        busy ? 'nd-action-busy' : ''
      }`.trim()}
      disabled={Boolean(disabled || busy)}
      aria-busy={busy}
    >
      {busy && (
        <LoaderCircle
          size={16}
          className="nd-spinner"
          aria-hidden="true"
        />
      )}
      {children}
    </button>
  );
}

const symbols = {
  working: LoaderCircle,
  success: CheckCircle2,
  warning: AlertCircle,
  error: AlertCircle,
  info: Info,
};

export function FeedbackHub() {
  const [items, setItems] = useState(notices);

  useEffect(() => {
    listeners.add(setItems);
    setItems([...notices]);

    return () => listeners.delete(setItems);
  }, []);

  if (items.length === 0) return null;

  return (
    <aside
      className="nd-feedback-stack"
      aria-label="Recent action feedback"
    >
      {items.map(item => {
        const Icon = symbols[item.kind] || Info;

        return (
          <div
            key={item.id}
            className={`nd-feedback nd-feedback-${item.kind}`}
            role={item.kind === 'error' ? 'alert' : 'status'}
          >
            <Icon
              size={20}
              className={
                item.kind === 'working' ? 'nd-spinner' : ''
              }
              aria-hidden="true"
            />

            <div className="nd-feedback-text">
              <strong>{item.title}</strong>

              {item.detail && <span>{item.detail}</span>}

              {item.kind === 'working' && (
                <div
                  className="nd-progress"
                  aria-label="Working"
                />
              )}
            </div>

            <button
              type="button"
              className="nd-feedback-close"
              onClick={() => dismissNotice(item.id)}
              aria-label={`Dismiss ${item.title}`}
            >
              <X size={16} />
            </button>
          </div>
        );
      })}
    </aside>
  );
}
