
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  rankRegionalProbes,
} from './vpsLatency.mjs';

test('ranks qualifying actual measurements', () => {
  const results = rankRegionalProbes({
    results: [
      {
        provider: 'Oracle',
        region: 'r1',
        location: 'London',
        attempts: 3,
        successful: 3,
        median_ms: 105,
      },
      {
        provider: 'AWS',
        region: 'r2',
        location: 'Cape Town',
        attempts: 3,
        successful: 2,
        median_ms: 83,
      },
    ],
  });

  assert.deepEqual(
    results.map(x => x.location),
    ['Cape Town', 'London']
  );
});

test(
  'ignores failed, single-shot, invalid and unsupported endpoints',
  () => {
    const results = rankRegionalProbes({
      results: [
        {
          provider: 'AWS',
          region: 'a',
          location: 'A',
          attempts: 3,
          successful: 1,
          median_ms: 2,
        },
        {
          provider: 'AWS',
          region: 'b',
          location: 'B',
          attempts: 3,
          successful: 3,
          median_ms: NaN,
        },
        {
          provider: 'Other',
          region: 'c',
          location: 'C',
          attempts: 3,
          successful: 3,
          median_ms: 1,
        },
        {
          provider: 'Oracle',
          region: 'd',
          location: 'D',
          attempts: 2,
          successful: 3,
          median_ms: 4,
        },
        {
          provider: 'AWS',
          region: 'e',
          location: 'E',
          attempts: 3,
          successful: 3,
          median_ms: 44,
        },
      ],
    });

    assert.deepEqual(
      results.map(x => x.location),
      ['E']
    );
  }
);

test('never fabricates a winner', () => {
  assert.deepEqual(
    rankRegionalProbes(null),
    []
  );

  assert.deepEqual(
    rankRegionalProbes({ results: [] }),
    []
  );
});
