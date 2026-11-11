
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  analyzeDisconnects,
  sessionSamples,
} from './disconnectAnalysis.mjs';

const start = '2026-11-10T15:00:00Z';

const sample = (minute, state, gateway_reply = null) => ({
  checked_at: `2026-11-10T15:${minute}:00Z`,
  state,
  gateway_reply,
});

test('prior session and malformed samples are excluded', () => {
  const status = {
    samples: [
      sample('00', 'ok'),
      sample('01', 'failed'),
      { state: 'failed', checked_at: 'bad' },
    ],
  };

  assert.equal(
    sessionSamples(status, '2026-11-10T15:00:30Z').length,
    1
  );
});

test('empty watch never claims a fault', () => {
  const result = analyzeDisconnects({
    samples: [],
    running: true,
  }, start);

  assert.match(result.headline, /No connection checks/);
  assert.equal(result.count, 0);
});

test('two failed targets do not automatically mean ISP outage', () => {
  const result = analyzeDisconnects({
    samples: [
      sample('00', 'ok'),
      sample('01', 'failed'),
    ],
  }, start);

  assert.match(result.headline, /failed in 1 check/);
  assert.match(
    result.facts.join(' '),
    /1 checks: neither/
  );
  assert.doesNotMatch(
    result.headline,
    /ISP|router fault/i
  );
});

test('router reply is supporting evidence only', () => {
  const result = analyzeDisconnects({
    samples: [sample('01', 'failed', true)],
  }, start);

  assert.match(
    result.facts.join(' '),
    /router still answered/
  );

  assert.match(result.next, /another device/);
});

test('one failed destination is not a broad outage', () => {
  const result = analyzeDisconnects({
    samples: [sample('00', 'mixed')],
  }, start);

  assert.match(
    result.headline,
    /One internet destination failed/
  );

  assert.match(result.next, /does not establish/);
});

test('successful checks describe only the observed window', () => {
  const result = analyzeDisconnects({
    samples: [
      sample('00', 'ok'),
      sample('01', 'ok'),
    ],
  }, start);

  assert.match(result.headline, /all 2/);
  assert.match(result.next, /does not rule out/);
});

test('route change takes priority over clean results', () => {
  const result = analyzeDisconnects({
    samples: [sample('00', 'ok')],
    message:
      'Network configuration changed. This watch ended ' +
      'to avoid mixing results from different connections.',
  }, start);

  assert.match(
    result.headline,
    /configuration changed/
  );
});
