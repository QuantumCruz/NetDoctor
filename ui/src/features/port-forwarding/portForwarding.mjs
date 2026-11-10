
/** IPv4 facts and user-facing port-forwarding conclusions. No network calls. */
export function classifyWan(value) {
  if (typeof value !== 'string') return null;

  const parts = value.trim().split('.');
  if (
    parts.length !== 4 ||
    parts.some(part => !/^\d{1,3}$/.test(part) || (part.length > 1 && part[0] === '0'))
  ) return null;

  const [a, b, c, d] = parts.map(Number);
  if (
    [a, b, c, d].some(n => n > 255) ||
    a === 0 || a === 127 || a >= 224 ||
    (a === 169 && b === 254)
  ) return null;

  if (a === 10) return { kind: 'private', range: '10.0.0.0/8' };
  if (a === 172 && b >= 16 && b <= 31) {
    return { kind: 'private', range: '172.16.0.0/12' };
  }
  if (a === 192 && b === 168) {
    return { kind: 'private', range: '192.168.0.0/16' };
  }
  if (a === 100 && b >= 64 && b <= 127) {
    return { kind: 'shared', range: '100.64.0.0/10' };
  }
  return { kind: 'other', range: 'Outside common private and shared IPv4 ranges' };
}

export function getPortForwardingAnswer(wanInfo, report, connection) {
  if (!wanInfo) return null;

  if (wanInfo.kind === 'private' || wanInfo.kind === 'shared') {
    const privateWan = wanInfo.kind === 'private';
    const reason = privateWan
      ? `Your router's WAN address is in ${wanInfo.range}, a private IPv4 range. The public internet cannot route incoming IPv4 traffic directly to it.`
      : `Your router's WAN address is in ${wanInfo.range}, a shared carrier IPv4 range. The public internet cannot route incoming IPv4 traffic directly to it.`;

    let action = 'Incoming traffic must also be forwarded by the upstream network. Identify whether that is another router or your ISP.';
    if (connection === 'isp') {
      action = 'Contact your ISP. Request a publicly reachable IPv4 address or an ISP-managed inbound port mapping.';
    } else if (connection === 'router') {
      action = 'Check the upstream router. It must also forward traffic to this router, or use a suitable bridge configuration. Check its WAN address as well.';
    }

    return {
      headline: 'Confirmed: your router does not have a public WAN IPv4 address',
      reason,
      action,
      barrier: 'Port forwarding on this router alone cannot make an application reachable from the public IPv4 internet.',
    };
  }

  if (report?.nat_status === 'No upstream IPv4 NAT indicated') {
    return {
      headline: 'Confirmed: the WAN and observed public IPv4 addresses match',
      reason: 'Both addresses match, but that does not prove a particular port is open.',
      action: 'Check the port-forwarding rule, target device IP, firewall and listening application. Then test from a different network.',
    };
  }
  if (report?.nat_status === 'Addresses differ — cause unverified') {
    return {
      headline: 'Confirmed: your WAN and observed public IPv4 addresses differ',
      reason: 'The two addresses do not match. This proves a mismatch, not which network device caused it.',
      action: 'Check for VPNs, proxies and additional routers. Confirm your public IPv4 assignment with your ISP.',
    };
  }
  if (report?.nat_status === 'IPv4 comparison unavailable') {
    return {
      headline: 'An IPv4 comparison could not be completed',
      reason: 'The external lookup returned IPv6. It cannot be compared directly with your router WAN IPv4.',
      action: 'Verify your external IPv4 without a VPN or proxy, or ask your ISP about your public IPv4 assignment.',
    };
  }

  return {
    headline: 'An external IPv4 comparison is still needed',
    reason: 'This WAN address is outside the common private and shared ranges. That does not by itself prove public reachability.',
    action: 'Verify the external IPv4 address. Then check the forwarding rule, firewall and listening application.',
  };
}
