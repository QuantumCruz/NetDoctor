
import assert from 'node:assert/strict';
import test from 'node:test';
import { classifyWan, getPortForwardingAnswer } from './portForwarding.mjs';

test('private WAN ranges are classified precisely', () => {
  assert.deepEqual(classifyWan('10.48.179.133'), {
    kind: 'private',
    range: '10.0.0.0/8',
  });
  assert.equal(classifyWan('172.16.0.1').kind, 'private');
  assert.equal(classifyWan('172.31.255.254').kind, 'private');
  assert.equal(classifyWan('192.168.0.1').kind, 'private');
  assert.equal(classifyWan('172.32.0.1').kind, 'other');
});

test('carrier-shared range does not swallow ordinary addresses', () => {
  assert.equal(classifyWan('100.64.0.1').kind, 'shared');
  assert.equal(classifyWan('100.127.255.254').kind, 'shared');
  assert.equal(classifyWan('100.128.0.1').kind, 'other');
});

test('invalid WAN addresses are rejected', () => {
  for (const ip of [
    '127.0.0.1',
    '169.254.2.1',
    '224.0.0.1',
    '1.2.3.999',
    '10.048.1.1',
    '10.1.2',
    '',
  ]) {
    assert.equal(classifyWan(ip), null, ip);
  }
});

test('private WAN confirms upstream barrier without declaring CGNAT', () => {
  const answer = getPortForwardingAnswer(
    classifyWan('10.48.179.133'),
    null,
    'isp'
  );

  assert.match(answer.headline, /Confirmed/);
  assert.match(answer.reason, /private IPv4/);
  assert.match(answer.reason, /does not establish CGNAT/);
  assert.match(answer.action, /Contact your ISP/);
  assert.match(answer.barrier, /alone cannot/);
});

test('another router changes next action', () => {
  const answer = getPortForwardingAnswer(
    classifyWan('192.168.1.2'),
    null,
    'router'
  );

  assert.match(answer.action, /upstream router/i);
  assert.equal(answer.alternatives[0].key, 'upstream-router');
});

test('matching public addresses do not prove a port is open', () => {
  const answer = getPortForwardingAnswer(
    classifyWan('8.8.8.8'),
    { nat_status: 'No upstream IPv4 NAT indicated' },
    'unknown'
  );

  assert.match(answer.reason, /does not prove/i);
  assert.deepEqual(answer.alternatives, []);
});

test('mismatched public addresses are not automatically CGNAT', () => {
  const answer = getPortForwardingAnswer(
    classifyWan('8.8.8.8'),
    { nat_status: 'Addresses differ — cause unverified' },
    'unknown'
  );

  assert.match(answer.reason, /mismatch/i);
  assert.doesNotMatch(answer.headline, /CGNAT/i);
  assert.deepEqual(answer.alternatives, []);
});

test('carrier-shared WAN gives a strong CGNAT clue', () => {
  const answer = getPortForwardingAnswer(
    classifyWan('100.81.1.2'),
    null,
    'isp'
  );

  assert.match(answer.reason, /strongly suggests CGNAT/);
  assert.match(answer.barrier, /alone cannot/);
});

test('private overlay option requires participating devices', () => {
  const answer = getPortForwardingAnswer(
    classifyWan('100.81.1.2'),
    null,
    'unknown'
  );

  const overlay = answer.alternatives.find(
    item => item.key === 'private-overlay'
  );

  assert.match(overlay.detail, /Each participating device/);
  assert.match(overlay.detail, /does not open a public port/);

  assert.deepEqual(
    overlay.links.map(item => item.label),
    ['Tailscale sharing', 'ZeroTier setup']
  );
});

test('public hosting is distinguished from private VPN networking', () => {
  const answer = getPortForwardingAnswer(
    classifyWan('100.81.1.2'),
    null,
    'isp'
  );

  assert.equal(answer.alternatives[0].key, 'isp-public-ip');

  const relay = answer.alternatives.find(
    item => item.key === 'public-relay'
  );

  assert.match(relay.detail, /TCP or UDP/);
  assert.match(relay.detail, /not a public hosting solution/);
});

test('no upstream NAT evidence means no unsupported overlay advice', () => {
  const answer = getPortForwardingAnswer(
    classifyWan('8.8.8.8'),
    null,
    'unknown'
  );

  assert.deepEqual(answer.alternatives, []);
});
