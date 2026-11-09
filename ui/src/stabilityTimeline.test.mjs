import test from 'node:test';
import assert from 'node:assert/strict';

import {
  MAX_DISPLAYED,
  prepareStabilityTimeline,
} from './stabilityTimeline.mjs';

const sample = (
  time,
  first_ok,
  second_ok,
  gateway_reply = null
) => ({
  checked_at: new Date(time).toISOString(),
  state:
    first_ok && second_ok
      ? 'ok'
      : first_ok || second_ok
        ? 'mixed'
        : 'failed',
  first_ok,
  second_ok,
  gateway_reply,
});

const start = Date.parse(
  '2026-11-07T13:00:00Z'
);

test('missing input produces no imaginary samples', () => {
  const result = prepareStabilityTimeline(null);

  assert.equal(result.points.length, 0);

  assert.deepEqual(result.counts, {
    ok: 0,
    mixed: 0,
    failed: 0,
    gatewayUnknown: 0,
  });

  assert.equal(result.gaps.length, 0);
});

test('samples are chronological and statuses come from actual TCP results', () => {
  const list = [
    sample(start + 20000, false, false, false),
    sample(start, true, true, true),
    sample(start + 10000, true, false),
  ];

  const result = prepareStabilityTimeline(list);

  assert.deepEqual(
    result.points.map(item => item.state),
    ['ok', 'mixed', 'failed']
  );

  assert.deepEqual(result.counts, {
    ok: 1,
    mixed: 1,
    failed: 1,
    gatewayUnknown: 1,
  });

  assert.equal(result.gaps.length, 0);
});

test('unobserved periods are marked separately from unsuccessful checks', () => {
  const result = prepareStabilityTimeline(
    [
      sample(start, true, true),
      sample(start + 90000, false, false),
    ],
    10,
    null
  );

  assert.equal(result.gaps.length, 1);
  assert.equal(
    result.gaps[0].durationSeconds,
    90
  );
  assert.equal(result.counts.failed, 1);
});

test('limited window is anchored to the most recently observed check, not current time', () => {
  const result = prepareStabilityTimeline(
    [
      sample(start, true, true),
      sample(start + 1200000, true, true),
      sample(start + 1800000, true, true),
    ],
    10,
    15
  );

  assert.equal(result.points.length, 2);
  assert.equal(
    result.lastMs,
    start + 1800000
  );
  assert.equal(result.availableCount, 3);
});

test('display never exceeds stored view capacity', () => {
  const list = Array.from(
    { length: 151 },
    (_, i) =>
      sample(start + i * 10000, true, true)
  );

  const result = prepareStabilityTimeline(
    list,
    10,
    null
  );

  assert.equal(
    result.points.length,
    MAX_DISPLAYED
  );

  assert.equal(
    result.firstMs,
    start + 31 * 10000
  );
});

test('invalid samples are skipped rather than treated as failures', () => {
  const result = prepareStabilityTimeline([
    null,
    {
      checked_at: 'not a date',
      first_ok: false,
      second_ok: false,
    },
    {
      checked_at: new Date(start).toISOString(),
      first_ok: 'false',
      second_ok: false,
    },
    sample(start, true, false, null),
  ]);

  assert.equal(result.points.length, 1);
  assert.equal(result.counts.mixed, 1);
});

test('a single sample has nonzero chart domain', () => {
  const result = prepareStabilityTimeline([
    sample(start, true, true),
  ]);

  assert.ok(
    result.domainMax > result.domainMin
  );

  assert.equal(result.ticks.length, 5);
});

test('a silent gateway remains unknown as to cause', () => {
  const result = prepareStabilityTimeline([
    sample(start, true, true, false),
  ]);

  assert.equal(
    result.points[0].gateway_reply,
    false
  );

  assert.equal(
    result.points[0].state,
    'ok'
  );
});