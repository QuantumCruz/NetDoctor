
import assert from 'node:assert/strict';
import test from 'node:test';
import { classifyWan, getPortForwardingAnswer } from './portForwarding.mjs';

test('private WAN ranges are classified precisely', () => {
  assert.deepEqual(classifyWan('10.48.179.133'), { kind: 'private', range: '10.0.0.0/8' });
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
  for (const ip of ['127.0.0.1', '169.254.2.1', '224.0.0.1', '1.2.3.999', '10.048.1.1', '10.1.2', '']) {
    assert.equal(classifyWan(ip), null, ip);
  }
});

test('private WAN gives a definite address finding without needing a lookup', () => {
  const wan = classifyWan('10.48.179.133');
  const answer = getPortForwardingAnswer(wan, null, 'isp');
  assert.match(answer.headline, /Confirmed/);
  assert.match(answer.reason, /private IPv4/);
  assert.match(answer.action, /Contact your ISP/);
  assert.match(answer.barrier, /alone cannot/);
});

test('connection type changes the next action, not the address classification', () => {
  const wan = classifyWan('192.168.1.2');
  const behindRouter = getPortForwardingAnswer(wan, null, 'router');
  assert.match(behindRouter.action, /upstream router/i);
  assert.match(behindRouter.headline, /Confirmed/);
});

test('matching public addresses do not prove a port is open', () => {
  const wan = classifyWan('8.8.8.8');
  const result = getPortForwardingAnswer(wan, { nat_status: 'No upstream IPv4 NAT indicated' }, 'unknown');
  assert.match(result.reason, /does not prove/i);
});

test('different public addresses establish a mismatch, not automatic CGNAT', () => {
  const wan = classifyWan('8.8.8.8');
  const result = getPortForwardingAnswer(wan, { nat_status: 'Addresses differ — cause unverified' }, 'unknown');
  assert.match(result.reason, /mismatch/i);
  assert.doesNotMatch(result.headline, /CGNAT/i);
});
