
/**
 * Rank measured AWS/Oracle HTTPS TCP handshakes.
 * Results are not actual VPS ping measurements.
 */
export function rankRegionalProbes(report) {
  if (!Array.isArray(report?.results)) return [];

  return report.results
    .filter(item =>
      item &&
      ['AWS', 'Oracle'].includes(item.provider) &&
      typeof item.location === 'string' &&
      item.location.trim() &&
      typeof item.region === 'string' &&
      item.region.trim() &&
      Number.isInteger(item.attempts) &&
      item.attempts >= 2 &&
      Number.isInteger(item.successful) &&
      item.successful >= 2 &&
      item.successful <= item.attempts &&
      typeof item.median_ms === 'number' &&
      Number.isFinite(item.median_ms) &&
      item.median_ms >= 0
    )
    .sort(
      (a, b) =>
        a.median_ms - b.median_ms ||
        a.location.localeCompare(b.location)
    );
}
