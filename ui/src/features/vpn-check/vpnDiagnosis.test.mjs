
import assert from 'node:assert/strict';
import test from 'node:test';

import { compareVpnExit } from './vpnDiagnosis.mjs';

const base = {
  public_ip: '41.1.2.3',
  ip_family: 'IPv4',
  country: 'Nigeria',
  country_code: 'NG',
};

test('changed IP and country are individually confirmed', () => {
  const result = compareVpnExit(base, {
    public_ip: '51.1.2.3',
    ip_family: 'IPv4',
    country: 'United Kingdom',
    country_code: 'GB',
  });

  assert.equal(result.changed, true);
  assert.equal(result.countryChanged, true);
  assert.match(result.headline, /public IP changed/);
  assert.match(
    result.location,
    /Nigeria to United Kingdom/
  );
  assert.doesNotMatch(
    result.headline,
    /encrypted|leak-free/
  );
});

test('changed IP but same country stays explicit', () => {
  const result = compareVpnExit(base, {
    ...base,
    public_ip: '41.2.3.4',
  });

  assert.equal(result.changed, true);
  assert.equal(result.countryChanged, false);
});

test('unchanged IP does not establish VPN functionality', () => {
  const result = compareVpnExit(base, {
    ...base,
  });

  assert.equal(result.changed, false);
  assert.match(
    result.headline,
    /No public IP change/
  );
});

test('different address families are not falsely compared', () => {
  const result = compareVpnExit(base, {
    public_ip: '2001:4860::1',
    ip_family: 'IPv6',
    country_code: 'GB',
  });

  assert.equal(result.changed, null);
  assert.match(
    result.headline,
    /different IP versions/
  );
});

test('missing country information does not become a location claim', () => {
  const result = compareVpnExit(base, {
    public_ip: '51.2.3.4',
    ip_family: 'IPv4',
  });

  assert.equal(result.countryChanged, null);
  assert.match(
    result.location,
    /not return enough/
  );
});

test('changed country label but same IP does not prove new VPN exit', () => {
  const result = compareVpnExit(base, {
    ...base,
    country: 'Ghana',
    country_code: 'GH',
  });

  assert.match(
    result.location,
    /do not establish a VPN exit change/
  );
});

test('invalid or missing reports are rejected', () => {
  assert.throws(
    () => compareVpnExit(null, base),
    /required/
  );

  assert.throws(
    () => compareVpnExit(base, {
      public_ip: '8.8.8.8',
    }),
    /required/
  );
});
