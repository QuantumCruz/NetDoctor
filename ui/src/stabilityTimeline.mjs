/** Pure preparation of real stability observations for the dashboard. */

export const MAX_DISPLAYED = 120;

function validSample(sample) {
  return sample && typeof sample === 'object' &&
    typeof sample.checked_at === 'string' &&
    Number.isFinite(Date.parse(sample.checked_at)) &&
    typeof sample.first_ok === 'boolean' &&
    typeof sample.second_ok === 'boolean' &&
    (
      sample.gateway_reply === true ||
      sample.gateway_reply === false ||
      sample.gateway_reply === null ||
      sample.gateway_reply === undefined
    );
}

export function prepareStabilityTimeline(
  samples,
  intervalSeconds = 10,
  windowMinutes = 30
) {
  const interval =
    Number.isFinite(intervalSeconds) && intervalSeconds > 0
      ? Math.min(intervalSeconds, 3600) * 1000
      : 10_000;

  const requested = Array.isArray(samples) ? samples : [];

  const ordered = requested
    .filter(validSample)
    .map((sample, originalIndex) => ({
      ...sample,
      timeMs: Date.parse(sample.checked_at),
      originalIndex,
      state: sample.first_ok && sample.second_ok
        ? 'ok'
        : sample.first_ok || sample.second_ok
          ? 'mixed'
          : 'failed',
      gateway_reply: sample.gateway_reply ?? null,
    }))
    .sort(
      (a, b) =>
        a.timeMs - b.timeMs ||
        a.originalIndex - b.originalIndex
    )
    .slice(-MAX_DISPLAYED);

  const last = ordered.at(-1)?.timeMs ?? null;

  const windowIsLimited =
    Number.isFinite(windowMinutes) && windowMinutes > 0;

  const cutoff =
    last !== null && windowIsLimited
      ? last - windowMinutes * 60_000
      : -Infinity;

  const points = ordered.filter(
    point => point.timeMs >= cutoff
  );

  const first = points[0]?.timeMs ?? null;
  const end = points.at(-1)?.timeMs ?? null;

  const domainMin =
    first === null
      ? 0
      : first === end
        ? first - interval / 2
        : first;

  const domainMax =
    end === null
      ? interval
      : first === end
        ? end + interval / 2
        : end;

  const gaps = [];

  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const deltaMs = current.timeMs - previous.timeMs;

    if (deltaMs > interval * 1.8) {
      gaps.push({
        fromMs: previous.timeMs,
        toMs: current.timeMs,
        durationSeconds: Math.round(deltaMs / 1000),
      });
    }
  }

  const counts = {
    ok: 0,
    mixed: 0,
    failed: 0,
    gatewayUnknown: 0,
  };

  for (const point of points) {
    counts[point.state] += 1;

    if (point.gateway_reply === null) {
      counts.gatewayUnknown += 1;
    }
  }

  const ticks = Array.from(
    { length: 5 },
    (_, index) =>
      domainMin +
      (domainMax - domainMin) * index / 4
  );

  return {
    points,
    gaps,
    counts,
    firstMs: first,
    lastMs: end,
    domainMin,
    domainMax,
    ticks,
    availableCount: ordered.length,
  };
}