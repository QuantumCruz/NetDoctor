
import assert from 'node:assert/strict';
import test from 'node:test';

import { interpretWebsite } from './websiteDiagnosis.mjs';

function result(website, internet = 'confirmed') {
  return {
    website: {
      target: 'https://github.com/',
      stage: 'complete',
      ...website,
    },
    steps: [
      { key: 'internet', status: internet },
    ],
  };
}

test('200 confirms only the tested HTTPS request', () => {
  const answer = interpretWebsite(
    result({ status: 'responded', http_status: 200 })
  );

  assert.match(answer.headline, /HTTP 200/);
  assert.match(answer.finding, /metadata-only/);
  assert.doesNotMatch(answer.finding, /browser works/);
});

test('301 confirms redirect without claiming redirected target works', () => {
  assert.match(
    interpretWebsite(result({ http_status: 301 })).finding,
    /did not follow/
  );
});

test('103 is an interim response, not a successful page load', () => {
  assert.match(
    interpretWebsite(
      result({
        http_status: 103,
        status: 'inconclusive',
      })
    ).finding,
    /interim/
  );
});

test('403 confirms access response rather than internet outage', () => {
  assert.match(
    interpretWebsite(result({ http_status: 403 })).finding,
    /rejected this request/
  );
});

test('404 identifies missing path', () => {
  assert.match(
    interpretWebsite(result({ http_status: 404 })).next,
    /path/
  );
});

test('405 is not classified as website down', () => {
  const answer = interpretWebsite(
    result({
      status: 'inconclusive',
      http_status: 405,
    })
  );

  assert.match(answer.finding, /not proof/);
});

test('500 reports server response and no invented root cause', () => {
  assert.match(
    interpretWebsite(result({ http_status: 503 })).finding,
    /does not establish/
  );
});

test('DNS failure remains an observation, not an ISP diagnosis', () => {
  const answer = interpretWebsite(
    result({
      stage: 'dns',
      status: 'inconclusive',
      explanation: 'No public address',
    })
  );

  assert.match(answer.headline, /lookup/);
  assert.doesNotMatch(answer.headline, /ISP/);
});

test('TCP failure and general mixed results are stated separately', () => {
  const answer = interpretWebsite(
    result({
      stage: 'tcp',
      status: 'inconclusive',
    }, 'mixed')
  );

  assert.match(answer.headline, /did not complete/);
  assert.match(answer.generalFinding, /some/);
});

test('second device works means investigate this computer first', () => {
  assert.match(
    interpretWebsite(
      result({ http_status: 200 }),
      'works'
    ).next,
    /On this computer/
  );
});

test('second device also fails means check another network', () => {
  assert.match(
    interpretWebsite(
      result({ http_status: 200 }),
      'fails'
    ).next,
    /mobile data/
  );
});

test('missing report is rejected instead of inventing findings', () => {
  assert.throws(
    () => interpretWebsite({}),
    /required/
  );
});
