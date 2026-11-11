
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  assessInternetFault,
} from './internetFault.mjs';

const step = (
  key,
  status,
  evidence = `${key} measured`
) => ({
  key,
  title: key,
  status,
  evidence,
});

const make = ({
  local = 'confirmed',
  dns = 'confirmed',
  internet = 'confirmed',
  website = 'not_tested',
} = {}) => ({
  tested_at: '2026-11-10T17:00:00+00:00',
  steps: [
    step('local', local),
    step('dns', dns),
    step('internet', internet),
    step('website', website),
  ],
});

const assess = (settings, comparisons) =>
  assessInternetFault(
    make(settings),
    comparisons
  );

test('successful public HTTPS does not claim an outage', () => {
  const result = assess();

  assert.equal(result.key, 'basic_access');
  assert.match(
    result.interpretation,
    /does not prove every website/
  );
});

test('missing active adapter is a local lead, not proven PC defect', () => {
  const result = assess({
    local: 'attention',
    internet: 'inconclusive',
  });

  assert.equal(result.key, 'pc_connection');
  assert.match(
    result.interpretation,
    /cannot yet assess the router or ISP/
  );
});

test('missing route does not prove ISP failure', () => {
  const result = assess({
    local: 'inconclusive',
    internet: 'inconclusive',
  });

  assert.equal(result.key, 'local_route');
  assert.match(
    result.interpretation,
    /does not establish an ISP outage/
  );
});

test('failed endpoints without comparisons remain unresolved', () => {
  const result = assess({
    internet: 'inconclusive',
  });

  assert.equal(result.key, 'unresolved');
  assert.match(
    result.interpretation,
    /None is established/
  );
});

test('working second device suggests PC-specific network path', () => {
  const result = assess(
    { internet: 'inconclusive' },
    { otherDevice: 'works' }
  );

  assert.equal(result.key, 'pc_path');
  assert.match(
    result.interpretation,
    /not a confirmed Windows or hardware fault/
  );
  assert.equal(
    result.evidence.at(-1).source,
    'reported'
  );
});

test('multiple failures plus working hotspot still cannot separate router and ISP', () => {
  const result = assess(
    { internet: 'inconclusive' },
    {
      otherDevice: 'fails',
      otherNetwork: 'works',
    }
  );

  assert.equal(result.key, 'shared_path');
  assert.match(
    result.interpretation,
    /does not distinguish the router from the ISP/
  );
});

test('another failed device alone does not establish ISP outage', () => {
  const result = assess(
    { internet: 'inconclusive' },
    { otherDevice: 'fails' }
  );

  assert.equal(result.key, 'shared_possible');
  assert.match(
    result.interpretation,
    /none is confirmed/
  );
});

test('working alternate network narrows to original path', () => {
  const result = assess(
    { internet: 'inconclusive' },
    { otherNetwork: 'works' }
  );

  assert.equal(result.key, 'original_network');
});

test('successful endpoint evidence takes precedence over outage report', () => {
  const result = assess(
    { internet: 'confirmed' },
    {
      otherDevice: 'fails',
      otherNetwork: 'works',
    }
  );

  assert.equal(result.key, 'basic_access');
});

test('mixed endpoints must not blame ISP', () => {
  const result = assess({
    internet: 'mixed',
  });

  assert.equal(result.key, 'destination');
  assert.match(
    result.interpretation,
    /does not by itself identify/
  );
});

test('responding website overrides total-failure assumptions', () => {
  const result = assess({
    internet: 'inconclusive',
    website: 'confirmed',
  });

  assert.equal(result.key, 'some_access');
});

test('inconclusive DNS is not proof when HTTPS works', () => {
  const result = assess({
    dns: 'inconclusive',
    internet: 'confirmed',
  });

  assert.equal(result.key, 'basic_access');
  assert.equal(result.actions.length, 2);
});

test('inconclusive DNS remains a possible explanation', () => {
  const result = assess({
    dns: 'inconclusive',
    internet: 'inconclusive',
  });

  assert.match(
    result.actions.at(-1),
    /policies or filtering/
  );
});

test('missing DNS stage does not invent DNS evidence', () => {
  const result = assessInternetFault({
    steps: [
      step('local', 'confirmed'),
      step('internet', 'inconclusive'),
    ],
  });

  assert.equal(result.evidence.length, 2);
});

test('requires local and internet diagnostic stages', () => {
  assert.throws(
    () => assessInternetFault(null),
    /required/
  );

  assert.throws(
    () => assessInternetFault({ steps: [] }),
    /missing required/
  );
});

test('rejects invalid comparison selections', () => {
  assert.throws(
    () => assess({}, {
      otherDevice: 'maybe',
    }),
    /Invalid/
  );
});

test('unknown stage status is not trusted as a success', () => {
  const result = assessInternetFault({
    steps: [
      step('local', 'confirmed'),
      step('internet', 'some_custom_status'),
    ],
  });

  assert.equal(result.key, 'unresolved');
  assert.equal(
    result.evidence[1].status,
    'Not established'
  );
});
