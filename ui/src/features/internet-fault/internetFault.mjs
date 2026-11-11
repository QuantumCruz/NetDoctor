
/**
 * Conservative fault isolation using NetDoctor's guided report.
 *
 * A single-PC snapshot cannot prove router failure or an ISP outage.
 * Cross-device and alternate-network answers are user-reported.
 * No network I/O or settings changes happen in this module.
 */

export const COMPARISON_CHOICES = Object.freeze([
  'unknown',
  'works',
  'fails',
]);

const STEP_KEYS = ['local', 'dns', 'internet'];

const STEP_STATUSES = new Set([
  'confirmed',
  'mixed',
  'attention',
  'inconclusive',
  'not_tested',
]);

const STATUS_TEXT = Object.freeze({
  confirmed: 'Observed',
  mixed: 'Mixed',
  attention: 'Needs attention',
  inconclusive: 'Not established',
  not_tested: 'Not tested',
});

function findStep(report, key) {
  const item = report.steps.find(step => step?.key === key);

  if (!item) return null;

  return {
    key,
    title:
      typeof item.title === 'string'
        ? item.title
        : key,
    status: STEP_STATUSES.has(item.status)
      ? item.status
      : 'inconclusive',
    evidence:
      typeof item.evidence === 'string'
        ? item.evidence
        : 'The check returned no detailed evidence.',
    next_step:
      typeof item.next_step === 'string'
        ? item.next_step
        : '',
  };
}

function outcome(key, headline, interpretation, actions) {
  return {
    key,
    headline,
    interpretation,
    actions,
  };
}

/**
 * otherDevice: another device on the SAME home network.
 * otherNetwork: THIS PC using a DIFFERENT connection.
 */
export function assessInternetFault(
  report,
  {
    otherDevice = 'unknown',
    otherNetwork = 'unknown',
  } = {},
) {
  if (!report || !Array.isArray(report.steps)) {
    throw new Error(
      'A completed NetDoctor diagnosis report is required.'
    );
  }

  if (
    !COMPARISON_CHOICES.includes(otherDevice) ||
    !COMPARISON_CHOICES.includes(otherNetwork)
  ) {
    throw new Error('Invalid comparison selection.');
  }

  const [local, dns, internet] = STEP_KEYS.map(
    key => findStep(report, key)
  );

  const website = findStep(report, 'website');

  if (!local || !internet) {
    throw new Error(
      'The diagnosis report is missing required checks.'
    );
  }

  const evidence = [local, dns, internet]
    .filter(Boolean)
    .map(step => ({
      key: step.key,
      label: ({
        local: 'PC connection and route',
        dns: 'Direct DNS lookup',
        internet: 'Public HTTPS connectivity',
      })[step.key],
      status: STATUS_TEXT[step.status],
      detail: step.evidence,
      source: 'measured',
    }));

  if (otherDevice !== 'unknown') {
    evidence.push({
      key: 'comparison_device',
      label: 'Another device on the same network',
      status: 'User-reported',
      detail: otherDevice === 'works'
        ? (
            'You reported that another device can use the ' +
            'internet on the same network.'
          )
        : (
            'You reported that another device also has ' +
            'internet trouble on the same network.'
          ),
      source: 'reported',
    });
  }

  if (otherNetwork !== 'unknown') {
    evidence.push({
      key: 'comparison_network',
      label: 'This PC on a different network',
      status: 'User-reported',
      detail: otherNetwork === 'works'
        ? (
            'You reported that this PC can use the ' +
            'internet through another connection.'
          )
        : (
            'You reported that this PC also has trouble ' +
            'through another connection.'
          ),
      source: 'reported',
    });
  }

  let selected;

  if (local.status === 'attention') {
    selected = outcome(
      'pc_connection',
      'Start with this PC’s connection',
      'Windows did not report an active network adapter ' +
        'during the check. NetDoctor cannot yet assess ' +
        'the router or ISP as the cause.',
      [
        'Check that Wi-Fi is connected or the Ethernet ' +
          'cable is attached, and that airplane mode is off.',
        'If Wi-Fi will not connect, compare with another ' +
          'device and try a different adapter or network ' +
          'before changing Windows settings.',
        'Run the diagnosis again after Windows shows ' +
          'an active connection.',
      ],
    );
  } else if (local.status === 'inconclusive') {
    selected = outcome(
      'local_route',
      'This PC’s local route needs checking',
      'Windows did not provide a usable default route ' +
        'in this snapshot. That can involve the PC’s ' +
        'configuration or its local network; it does ' +
        'not establish an ISP outage.',
      [
        'Check whether Windows has a valid IP address ' +
          'and a default gateway for the currently ' +
          'connected network.',
        otherDevice === 'works'
          ? (
              'Because you report another device works ' +
              'on the same network, focus on this PC’s ' +
              'Wi-Fi/Ethernet connection and IP configuration.'
            )
          : (
              'Compare another device on the same ' +
              'network to narrow the fault.'
            ),
        'Reconnect to the intended network and ' +
          'rerun the diagnosis.',
      ],
    );
  } else if (internet.status === 'confirmed') {
    selected = outcome(
      'basic_access',
      'Basic internet access worked during the test',
      'The tested public HTTPS endpoints accepted ' +
        'connections. This does not prove every ' +
        'website works or rule out slow or ' +
        'intermittent service.',
      [
        'If one website or app fails, use “Why won’t ' +
          'a website open?” to test that destination specifically.',
        'If speed or brief dropouts are the issue, ' +
          'use the Slow Internet or Disconnections ' +
          'check while the problem occurs.',
      ],
    );
  } else if (website?.status === 'confirmed') {
    selected = outcome(
      'some_access',
      'A website responded despite uncertain general checks',
      'An optional website check succeeded. That is ' +
        'evidence of some internet access, even if the ' +
        'standard test endpoints did not respond.',
      [
        'Repeat the check while the problem occurs. ' +
          'A successful website request means a universal ' +
          'outage has not been established.',
        'Check which specific services fail and ' +
          'compare them separately.',
      ],
    );
  } else if (internet.status === 'mixed') {
    selected = outcome(
      'destination',
      'Connectivity varied between destinations',
      'At least one public HTTPS test endpoint responded ' +
        'while another did not. This does not by itself ' +
        'identify a PC, router, or ISP failure.',
      [
        'Repeat the test to see whether the same ' +
          'destination fails again.',
        'If a specific service is affected, check ' +
          'that service separately from another connection.',
      ],
    );
  } else if (otherDevice === 'works') {
    selected = outcome(
      'pc_path',
      'Investigate this PC’s path to the network first',
      'NetDoctor could not verify public HTTPS access ' +
        'from this PC, while you reported that another ' +
        'device works on the same network. This points ' +
        'toward the PC or its individual connection to ' +
        'the router, not a confirmed Windows or hardware fault.',
      [
        'Compare Wi-Fi/Ethernet status, IP assignment, ' +
          'DNS, VPN and proxy settings on this PC. ' +
          'Do not reset everything automatically.',
        otherNetwork === 'works'
          ? (
              'You report this PC works on another connection, ' +
              'so check its configuration for the original ' +
              'network and that network’s Wi-Fi path.'
            )
          : (
              'If possible, test this same PC on a phone ' +
              'hotspot to narrow whether the issue follows the PC.'
            ),
        'Rerun NetDoctor while connected to the ' +
          'network that has the problem.',
      ],
    );
  } else if (
    otherDevice === 'fails' &&
    otherNetwork === 'works'
  ) {
    selected = outcome(
      'shared_path',
      'The home network or upstream connection needs checking',
      'NetDoctor could not verify public HTTPS access ' +
        'here. You report that another device also ' +
        'struggles on the home network, while this PC ' +
        'works on a different connection. This points ' +
        'toward a shared home-network or upstream issue, ' +
        'but does not distinguish the router from the ISP.',
      [
        'Check the router’s WAN/internet status and ' +
          'whether its upstream cable or modem reports a connection.',
        'If the router has no upstream connection, check ' +
          'the ISP’s outage/status information or contact ' +
          'support with the time and failed checks.',
        'If the router reports normal upstream access, ' +
          'investigate router configuration and local network ' +
          'connectivity before blaming the ISP.',
      ],
    );
  } else if (otherDevice === 'fails') {
    selected = outcome(
      'shared_possible',
      'The problem may affect your shared network',
      'NetDoctor could not confirm public HTTPS ' +
        'connectivity, and you report another device ' +
        'has the same problem. The router, upstream ' +
        'modem, ISP path, or local Wi-Fi could be involved; ' +
        'none is confirmed.',
      [
        'Check whether this PC can get online through ' +
          'a different connection, such as a phone hotspot.',
        'Look at the router’s WAN/internet status ' +
          'and cable/modem connection.',
        'If the upstream connection is down, contact ' +
          'the ISP and share the time of the failure ' +
          'and your test results.',
      ],
    );
  } else if (otherNetwork === 'works') {
    selected = outcome(
      'original_network',
      'The original network path needs checking',
      'The public HTTPS check on the original network ' +
        'was not confirmed, and you report that this PC ' +
        'works on another network. This narrows the ' +
        'investigation to the original connection, ' +
        'but does not prove the router or ISP is at fault.',
      [
        'Compare another device on the original network.',
        'Check Wi-Fi signal, router status and ' +
          'WAN/internet connection on the original network.',
        'Rerun NetDoctor on the original network ' +
          'after checking its status.',
      ],
    );
  } else {
    selected = outcome(
      'unresolved',
      'The available tests cannot identify the fault yet',
      'NetDoctor did not verify public HTTPS connectivity ' +
        'to its test endpoints. This may involve DNS, ' +
        'routing, filtering, the local network, the ISP ' +
        'path or the test destinations. None is established.',
      [
        'Check whether a second device works ' +
          'on the same network.',
        'If possible, test this PC on a different ' +
          'connection, such as a phone hotspot.',
        'Repeat the diagnosis while the problem is happening. ' +
          'Avoid resetting settings until there is ' +
          'a more specific clue.',
      ],
    );
  }

  // DNS is supporting evidence, not independent proof of failure.
  if (
    dns?.status === 'inconclusive' &&
    selected.key !== 'basic_access'
  ) {
    selected.actions.push(
      'Direct UDP DNS did not produce a confirmed response. ' +
      'That can also happen with DNS policies or filtering; ' +
      'test a real website before changing DNS settings.'
    );
  }

  return {
    ...selected,
    evidence,
    comparisonNote:
      'Other-device and hotspot comparisons are supplied by ' +
      'you; NetDoctor did not independently test those ' +
      'devices or connections.',
    limitation:
      'A short snapshot cannot independently certify a ' +
      'router hardware fault or an ISP outage. Gateway ' +
      'ICMP nonresponses alone are not proof of router ' +
      'failure; TCP checks do not measure speed or ' +
      'intermittent faults.',
    testedAt:
      typeof report.tested_at === 'string'
        ? report.tested_at
        : null,
  };
}
