
import { ArrowRight, Cable } from 'lucide-react';
import { compareConnectionSpeeds, routeType } from './slowInternet.mjs';

/** One controlled comparison. Uses the same test runner as the first reading. */
export default function SpeedComparison({
  first, firstOverview, second, secondOverview, busy, onTest,
}) {
  if (!first) return null;

  const comparison = second
    ? compareConnectionSpeeds(first, second, firstOverview, secondOverview)
    : null;

  return (
    <div style={{ marginTop: 20 }}>
      <strong>Check whether Wi-Fi is limiting your speed</strong>
      <p>
        Use the same computer and router. Connect the computer to the router
        with an Ethernet cable, disconnect Wi-Fi, then run the second test.
        Pause other downloads for both tests.
      </p>
      <p className="guided-caution">
        First test's Windows adapter: <strong>{firstOverview?.interface || 'Not identified'}</strong>.
        {routeType(firstOverview) !== 'wifi' && (
          <> Windows did not identify a Wi-Fi default route for that test.
            To compare Wi-Fi against Ethernet, retest on Wi-Fi first.</>
        )}
      </p>
      <div className="guided-buttons">
        <button
          type="button"
          className="guided-secondary"
          disabled={busy}
          onClick={onTest}
        >
          <Cable size={17} />
          {busy ? 'Testing connection…' : second ? 'Repeat Ethernet test' : 'Run Ethernet comparison'}
          <ArrowRight size={16} />
        </button>
      </div>
      {comparison && (
        <div className="guided-next-step" aria-live="polite">
          <strong>{comparison.headline}</strong>
          {comparison.facts.map(fact => <p key={fact}>{fact}</p>)}
          <p><strong>Next step:</strong> {comparison.next}</p>
          <p className="guided-caution">{comparison.caution}</p>
        </div>
      )}
    </div>
  );
}
