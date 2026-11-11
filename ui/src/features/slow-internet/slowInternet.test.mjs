
import assert from 'node:assert/strict';
import test from 'node:test';
import { readSpeed, validPlan, explainSpeed, routeType, compareConnectionSpeeds } from './slowInternet.mjs';

test('plan validation remains optional and bounded', () => {
  for (const value of ['', '100.5', ' 75 ']) assert.equal(validPlan(value), true);
  for (const value of ['0', '-2', '1e3', 'NaN', '100001', 'hello']) assert.equal(validPlan(value), false);
});

test('measurements do not invent missing speed values', () => {
  const report = readSpeed({ getDownloadBandwidth: () => 42_000_000, getUploadBandwidth: () => 8_000_000, getUnloadedLatency: () => 29 });
  assert.equal(report.download_mbps, 42);
  assert.equal(report.upload_mbps, 8);
  assert.equal(report.latency_ms, 29);
  assert.equal(readSpeed({}).download_mbps, null);
});

test('plan comparison stays factual', () => {
  const analysis = explainSpeed({ download_mbps: 25, upload_mbps: 5, latency_ms: 40 }, '100', {});
  assert.match(analysis.headline, /25%/);
  assert.match(analysis.next, /Ethernet/);
  assert.doesNotMatch(analysis.headline, /ISP fault/i);
});

test('Wi-Fi signal is only reported when Windows provided a valid connected reading', () => {
  const weak = explainSpeed({ download_mbps: 12 }, '', { network: { wifi: { status: 'Connected', signal_percent: 23 } } });
  assert.match(weak.facts.join(' '), /23%/);
  const unavailable = explainSpeed({ download_mbps: 12 }, '', { network: { wifi: { status: 'Connected (details unavailable)', signal_percent: 0 } } });
  assert.doesNotMatch(unavailable.facts.join(' '), /Wi-Fi signal strength/);
});

test('no advertised plan does not establish a speed fault', () => {
  const result = explainSpeed({ download_mbps: 90 }, '', { status: 'reachable' });
  assert.match(result.facts.join(' '), /No subscription/);
  assert.doesNotMatch(result.headline, /slow|failed/i);
});

test('route detection cannot call arbitrary adapter names Ethernet', () => {
  assert.equal(routeType({ interface: 'Wi-Fi' }), 'wifi');
  assert.equal(routeType({ interface: 'Ethernet' }), 'ethernet');
  assert.equal(routeType({ interface: 'Tailscale' }), 'unverified');
  assert.equal(routeType({ interface: 'Custom Adapter' }), 'unverified');
});

test('a verified Wi-Fi-to-Ethernet speed increase is reported numerically', () => {
  const result = compareConnectionSpeeds({ download_mbps: 20 }, { download_mbps: 60 }, { interface: 'Wi-Fi' }, { interface: 'Ethernet' });
  assert.equal(result.adapterNamesMatch, true);
  assert.match(result.headline, /40.0 Mbps faster/);
  assert.match(result.facts.join(' '), /200% higher/);
  assert.match(result.next, /Wi-Fi link/);
  assert.doesNotMatch(result.headline, /ISP fault/i);
});

test('when the second network is not verified the app does not attribute change to Wi-Fi', () => {
  const result = compareConnectionSpeeds({ download_mbps: 20 }, { download_mbps: 60 }, { interface: 'Wi-Fi' }, { interface: 'Tailscale' });
  assert.equal(result.adapterNamesMatch, false);
  assert.match(result.next, /Check which adapter Windows is using/);
});

test('equal results do not falsely imply the ISP is healthy', () => {
  const result = compareConnectionSpeeds({ download_mbps: 30 }, { download_mbps: 30 }, { interface: 'Wi-Fi' }, { interface: 'Ethernet' });
  assert.equal(result.adapterNamesMatch, true);
  assert.match(result.headline, /same download speed/);
  assert.doesNotMatch(result.headline, /healthy|fixed/i);
});

test('missing or bad comparative results are rejected', () => {
  assert.throws(() => compareConnectionSpeeds({ download_mbps: 10 }, { download_mbps: NaN }), /Two completed/);
});
