
import { ArrowRight, RotateCcw } from 'lucide-react';
import { getPortForwardingAnswer } from './portForwarding.mjs';

/** Present existing port-forwarding evidence and relevant next steps. */
export default function PortForwardingResult({
  wan, wanInfo, connection, setConnection, report,
  busy, error, onCompare, onRestart, onExploreTools,
}) {
  const answer = getPortForwardingAnswer(wanInfo, report, connection);
  const upstream = wanInfo.kind === 'private' || wanInfo.kind === 'shared';

  return (
    <>
      <strong className="guided-answer-title">{answer.headline}</strong>
      <p>{answer.reason}</p>

      {upstream && (
        <>
          <div className="guided-next-step">
            <strong>What this means for port forwarding</strong>
            <p>{answer.barrier}</p>
          </div>
          <div style={{ marginTop: 16 }}>
            <strong>How is your router connected?</strong>
            <div className="guided-buttons">
              {[
                ['isp', 'Directly to my ISP line'],
                ['router', 'Behind another router'],
                ['unknown', 'Not sure'],
              ].map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className="guided-secondary"
                  aria-pressed={connection === id}
                  onClick={() => setConnection(id)}
                >
                  {connection === id ? '✓ ' : ''}{label}
                </button>
              ))}
            </div>
          </div>
        </>
      )}

      <div className="guided-next-step">
        <strong>What to do next</strong>
        <p>{answer.action}</p>
      </div>

      {answer.alternatives?.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <strong>Ways to connect despite upstream NAT</strong>
          <p>
            Choose an option based on whether access is private
            (friends or your own devices) or public (anyone on the internet).
          </p>

          {answer.alternatives.map(option => (
            <div className="guided-details" key={option.key}>
              <strong>{option.title}</strong>
              <p>{option.detail}</p>

              {option.links?.map(link => (
                <p key={link.url}>
                  <a
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {link.label}
                  </a>
                </p>
              ))}
            </div>
          ))}

          <p className="guided-caution">
            Tailscale and ZeroTier require compatible devices and application
            support. NAT restrictions can also force relayed connections,
            which may add latency. NetDoctor has not tested these services
            on your network.
          </p>
        </div>
      )}

      <div style={{ marginTop: 17 }}>
        <strong>Evidence</strong>
        <p><strong>Router WAN:</strong> {wan.trim()}</p>
        <p><strong>Address range:</strong> {wanInfo.range}</p>
        <p><strong>Externally observed IP:</strong> {report?.public_ip || 'Not checked'}</p>

        {report && (
          <>
            <p><strong>IP version:</strong> {report.ip_family || 'Unknown'}</p>
            <p><strong>External network:</strong> {report.exit_network || 'Not identified'}</p>
            <p><strong>Comparison:</strong> {report.nat_status || 'Not determined'}</p>
          </>
        )}
      </div>

      {!report && (
        <>
          <p className="guided-caution">
            Optional: NetDoctor can look up your external IP using IP.SB.
            The service will see your public IP; your entered router WAN
            address stays on this computer. No settings are changed.
          </p>

          <div className="guided-buttons">
            <button
              type="button"
              className="guided-primary"
              onClick={onCompare}
              disabled={busy}
            >
              {busy ? 'Checking public address…' : 'Verify public address'}
              <ArrowRight size={16} />
            </button>
          </div>
        </>
      )}

      {error && (
        <p className="guided-error" role="alert">
          {error}
        </p>
      )}

      <p className="guided-caution">
        This does not test whether an inbound port is open.
        VPNs and proxies can change the external address observed by the lookup.
      </p>

      <details className="guided-details">
        <summary>Technical explanation</summary>
        <p>
          RFC 1918 defines private IPv4 ranges. RFC 6598 defines
          carrier-shared IPv4 space. These addresses cannot be
          reached directly from the public IPv4 internet.
        </p>
        <p>
          An actual port test needs a listening application and
          an incoming attempt from a separate network.
        </p>
      </details>

      <div className="guided-buttons">
        <button
          type="button"
          className="guided-primary"
          onClick={onRestart}
          disabled={busy}
        >
          Start again <RotateCcw size={16} />
        </button>

        <button
          type="button"
          className="guided-secondary"
          onClick={onExploreTools}
          disabled={busy}
        >
          Explore tools
        </button>
      </div>
    </>
  );
}
