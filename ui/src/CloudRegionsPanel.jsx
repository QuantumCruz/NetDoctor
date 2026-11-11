import { confirmInPage } from './confirmInPage.mjs';

import { useRef, useState } from 'react';
import {
  Cloud,
  Globe2,
  RefreshCw,
  Server,
  ShieldCheck,
} from 'lucide-react';
import {
  FeedbackButton,
  beginTask,
  notify,
} from './feedback.jsx';
import './cloud-regions.css';

const PROVIDERS = [
  { value: 'all', label: 'AWS + Oracle Cloud', count: 10 },
  { value: 'AWS', label: 'Amazon Web Services', count: 5 },
  { value: 'Oracle', label: 'Oracle Cloud', count: 5 },
];

function milliseconds(value) {
  return typeof value === 'number' && Number.isFinite(value)
    ? `${value.toFixed(2)} ms`
    : 'Unavailable';
}

function ProviderName({ provider }) {
  return (
    <span className={`cloud-provider cloud-provider-${provider?.toLowerCase()}`}>
      {provider === 'AWS' ? 'AWS' : 'Oracle Cloud'}
    </span>
  );
}

export default function CloudRegionsPanel() {
  const [provider, setProvider] = useState('all');
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const runningRef = useRef(false);

  async function runComparison() {
    if (runningRef.current) return;

    const api = window.pywebview?.api;

    if (!api?.check_cloud_regions) {
      setError(
        'Cloud-region comparisons require the updated Windows desktop application.'
      );
      notify(
        'warning',
        'Cloud comparison unavailable',
        'The desktop bridge is not ready.'
      );
      return;
    }

    const selected = PROVIDERS.find(item => item.value === provider);
    const count = selected?.count ?? 10;

    if (!(await confirmInPage({ title: 'Compare cloud regions?', message: (`NetDoctor will contact ${count} public cloud API endpoints ` +
      `over TCP port 443, with three connection attempts per endpoint. ` +
      `The endpoints may observe your public exit IP address. ` +
      `No large files are downloaded, no cloud accounts are required, ` +
      `and no network settings are changed. Continue?`).replace(/\s+(?:Continue\?|Start monitoring\?)$/, ''), confirmLabel: 'Measure regions' }))) {
      return;
    }

    runningRef.current = true;
    setBusy(true);
    setError('');

    const finish = beginTask(
      'Comparing cloud regions…',
      `Measuring connection setup times for ${count} endpoints.`
    );

    try {
      const response = await api.check_cloud_regions(provider);

      if (!response?.ok || !response.report) {
        const message =
          response?.error || 'Cloud-region comparison could not finish.';

        setError(message);
        finish('warning', 'Cloud comparison incomplete', message);
        return;
      }

      const next = response.report;

      if (!Array.isArray(next.results)) {
        throw new Error('Malformed comparison report');
      }

      setReport(next);

      const measured = next.results.filter(
        item => typeof item.median_ms === 'number'
      ).length;

      finish(
        measured > 0 ? 'success' : 'warning',
        'Cloud comparison completed',
        `${measured} of ${next.results.length} endpoints measured.`
      );
    } catch {
      setError(
        'Cloud-region comparison failed. Check your connection and retry.'
      );

      finish(
        'error',
        'Cloud comparison failed',
        'The requested comparison could not be completed.'
      );
    } finally {
      runningRef.current = false;
      setBusy(false);
    }
  }

  const results = report?.results || [];
  const best = report?.best_observed_endpoint;
  const successful = results.filter(
    item => item.median_ms != null
  ).length;
  const testedAt = report?.tested_at
    ? new Date(report.tested_at).toLocaleString()
    : '';

  return (
    <section className="cloud-page">
      <div className="cloud-intro panel">
        <div className="cloud-intro-heading">
          <div className="cloud-icon">
            <Cloud size={27} />
          </div>

          <div>
            <p className="eyebrow">ON-DEMAND NETWORK TEST</p>
            <h2>Compare cloud regions</h2>
            <p>
              Discover which tested cloud API endpoints respond
              fastest from your current connection.
            </p>
          </div>
        </div>

        <div className="cloud-controls">
          <label htmlFor="cloud-provider-select">
            Providers
          </label>

          <div className="cloud-actions">
            <select
              id="cloud-provider-select"
              value={provider}
              disabled={busy}
              onChange={event => setProvider(event.target.value)}
            >
              {PROVIDERS.map(item => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>

            <FeedbackButton
              className="primary"
              onClick={runComparison}
              busy={busy}
            >
              <RefreshCw size={17} />
              {busy ? 'Comparing regions…' : 'Run comparison'}
            </FeedbackButton>
          </div>
        </div>

        <p className="cloud-privacy">
          <ShieldCheck size={17} />
          Runs only when requested. Three TCP attempts per endpoint.
          No cloud subscription, no large download, and no router changes.
        </p>

        {busy && (
          <div className="cloud-progress" role="status" aria-live="polite">
            <span className="cloud-progress-dot" />
            Testing selected endpoints. This may take several seconds.
            Results appear when the comparison finishes.
          </div>
        )}

        {error && (
          <p className="inline-warning" role="alert">
            {error}
          </p>
        )}
      </div>

      {!report && !busy && (
        <div className="cloud-empty panel">
          <Globe2 size={36} />
          <h3>No cloud-region measurements yet</h3>
          <p>
            Select a provider and run a comparison to see real
            network measurements.
          </p>
        </div>
      )}

      {report && (
        <>
          <div className="cloud-summary">
            <article className="cloud-stat panel">
              <span>FASTEST OBSERVED ENDPOINT</span>

              <strong>
                {best
                  ? best.location
                  : 'Not determined'}
              </strong>

              <p>
                {best
                  ? `${best.provider} · ${milliseconds(best.median_ms)}`
                  : 'Not enough successful samples to choose one.'}
              </p>
            </article>

            <article className="cloud-stat panel">
              <span>ENDPOINTS MEASURED</span>
              <strong>{successful} / {results.length}</strong>
              <p>
                At least one TCP connection completed.
              </p>
            </article>
          </div>

          <div className="panel cloud-results">
            <div className="cloud-results-heading">
              <div>
                <p className="eyebrow">MEASURED RESULTS</p>
                <h2>Regional responsiveness</h2>
                <p>
                  Sorted by measured TCP connection setup time.
                  Lower is better for this particular test.
                </p>
              </div>
            </div>

            <div className="cloud-table-scroll">
              <table className="cloud-table">
                <thead>
                  <tr>
                    <th scope="col">Region</th>
                    <th scope="col">Provider</th>
                    <th scope="col">Median TCP time</th>
                    <th scope="col">Connections</th>
                    <th scope="col">Sample variation</th>
                  </tr>
                </thead>

                <tbody>
                  {results.map(item => (
                    <tr key={`${item.provider}-${item.region}`}>
                      <td>
                        <strong>{item.location}</strong>
                        <span className="cloud-region-id">
                          {item.region}
                        </span>
                        <span className="cloud-region-host">
                          {item.hostname}
                        </span>
                      </td>

                      <td>
                        <ProviderName provider={item.provider} />
                      </td>

                      <td>
                        <strong className={
                          item.median_ms == null
                            ? 'cloud-unavailable'
                            : 'cloud-time'
                        }>
                          {milliseconds(item.median_ms)}
                        </strong>
                      </td>

                      <td>
                        <span className={
                          item.successful === item.attempts
                            ? 'cloud-connected'
                            : 'cloud-limited'
                        }>
                          {item.successful} / {item.attempts}
                        </span>
                      </td>

                      <td>
                        {item.variation_ms == null
                          ? 'Not enough samples'
                          : milliseconds(item.variation_ms)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {results.some(item => item.status !== 'measured') && (
              <p className="cloud-caution">
                One or more endpoints did not complete every connection.
                This is not a packet-loss measurement or proof that
                a cloud region is down.
              </p>
            )}

            <p className="cloud-measured-at">
              <Server size={15} />
              {report.method} · {testedAt}
            </p>
          </div>
        </>
      )}

      <div className="cloud-explanation panel">
        <h3>How should I interpret these results?</h3>

        <p>
          NetDoctor measures how long your computer takes to establish
          TCP connections to selected public cloud API endpoints.
          It does not measure the response time of every server
          hosted in those regions.
        </p>

        <p>
          A lower time can indicate a more responsive route to the
          tested endpoint. Small differences may be ordinary network
          variation, so repeat measurements before drawing conclusions.
        </p>

        <p>
          Connection failures may result from filtering, DNS issues,
          timeouts, or endpoint restrictions. They do not automatically
          indicate a regional outage.
        </p>

        <p className="disclaimer">
          {report?.disclaimer ||
            'Results are not guaranteed gaming latency, application performance, or cloud-provider rankings.'}
        </p>
      </div>
    </section>
  );
}
