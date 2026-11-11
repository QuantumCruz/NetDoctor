
/** Interpret this watch's recorded samples. No probes or guessed causes. */

export function sessionSamples(status, startedAt) {
  const start = Date.parse(startedAt);

  if (
    !Number.isFinite(start) ||
    !Array.isArray(status?.samples)
  ) {
    return [];
  }

  return status.samples.filter(sample => {
    if (
      !sample ||
      !['ok', 'mixed', 'failed'].includes(sample.state)
    ) {
      return false;
    }

    const recorded = Date.parse(sample.checked_at);

    return Number.isFinite(recorded) && recorded >= start;
  });
}

export function analyzeDisconnects(status, startedAt) {
  const samples = sessionSamples(status, startedAt);

  const ok = samples.filter(s => s.state === 'ok').length;
  const mixed = samples.filter(s => s.state === 'mixed').length;
  const failed = samples.filter(s => s.state === 'failed').length;

  const gatewayReplied = samples.filter(
    s => s.state === 'failed' && s.gateway_reply === true
  ).length;

  const routeChanged = /network configuration changed/i.test(
    status?.message ?? ''
  );

  const facts = [
    `${samples.length} checks recorded during this watch.`,
    `${ok} checks: both public TCP destinations responded.`,
    `${mixed} checks: only one public TCP destination responded.`,
    `${failed} checks: neither public TCP destination responded.`,
  ];

  if (gatewayReplied) {
    facts.push(
      `During ${gatewayReplied} unsuccessful public checks, ` +
      'the router still answered an ICMP echo request.'
    );
  }

  let headline;
  let next;

  if (routeChanged) {
    headline = 'Windows network configuration changed during the watch';

    next =
      'Check whether Windows switched Wi-Fi, Ethernet, VPN or gateway. ' +
      'Restart the watch on the intended connection to collect a clean set of results.';
  } else if (!samples.length) {
    headline = 'No connection checks recorded yet';

    next =
      'Keep the watch running while the problem occurs. ' +
      'No connection failure can be assessed without recorded checks.';
  } else if (failed) {
    headline =
      `Both internet test connections failed in ${failed} ` +
      (failed === 1 ? 'check' : 'checks');

    next = gatewayReplied
      ? (
          'Your router answered a ping during at least one unsuccessful ' +
          'public check. Check another device on the same network at the ' +
          'same time, then compare both devices before contacting your ISP.'
        )
      : (
          'Repeat the watch on a second device using the same network. ' +
          'If both devices lose public access together, check the router ' +
          'status and share the recorded times with your ISP.'
        );
  } else if (mixed) {
    headline =
      `One internet destination failed in ${mixed} ` +
      (mixed === 1 ? 'check' : 'checks');

    next =
      'Check whether the same website or application is affected. ' +
      'A one-destination failure does not establish a general internet disconnection.';
  } else {
    headline =
      `Both internet test connections succeeded in all ${ok} recorded checks`;

    next =
      'Keep monitoring while the disconnect happens. A clean sample window ' +
      'does not rule out interruptions at other times or in a particular application.';
  }

  return {
    headline,
    facts,
    next,
    count: samples.length,
    lastCheckedAt: samples.length
      ? samples[samples.length - 1].checked_at
      : null,
    note:
      'Each sample attempts TCP port 443 connections to 1.1.1.1 and ' +
      '8.8.8.8. Gateway ping is separate. Failed checks alone do ' +
      'not prove an ISP outage.',
  };
}
