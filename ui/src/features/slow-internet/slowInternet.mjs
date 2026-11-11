
/** Interpret real measurements. This module performs no network requests. */
export function readSpeed(results) {
  function value(method, divisor = 1) {
    try {
      const number = results?.[method]?.();
      return typeof number === 'number' && Number.isFinite(number) && number >= 0
        ? number / divisor : null;
    } catch {
      return null;
    }
  }

  return {
    download_mbps: value('getDownloadBandwidth', 1_000_000),
    upload_mbps: value('getUploadBandwidth', 1_000_000),
    latency_ms: value('getUnloadedLatency'),
    tested_at: new Date().toISOString(),
  };
}

export function validPlan(text) {
  if (typeof text !== 'string') return false;
  const value = text.trim();
  return value === '' || (/^\d+(?:\.\d+)?$/.test(value) && Number(value) > 0 && Number(value) <= 100000);
}

function validRate(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

export function explainSpeed(reading, planText, overview) {
  if (!validRate(reading?.download_mbps) || !validPlan(planText)) {
    throw new Error('Valid download measurement and optional plan are required.');
  }

  const download = reading.download_mbps;
  const plan = planText.trim() ? Number(planText) : null;
  const wifi = overview?.network?.wifi;
  const signal = wifi?.status === 'Connected' && validRate(wifi.signal_percent) && wifi.signal_percent <= 100
    ? wifi.signal_percent : null;

  const facts = [`Cloudflare measured ${download.toFixed(1)} Mbps download during this test.`];
  if (validRate(reading.upload_mbps)) facts.push(`Upload measured ${reading.upload_mbps.toFixed(1)} Mbps.`);
  if (validRate(reading.latency_ms)) facts.push(`Idle latency to the test network measured ${reading.latency_ms.toFixed(0)} ms.`);

  const percent = plan === null ? null : (download / plan) * 100;
  if (percent !== null) {
    facts.push(`That is ${percent.toFixed(0)}% of the ${plan} Mbps plan you entered. An advertised maximum is not a guaranteed Wi-Fi measurement.`);
  } else {
    facts.push('No subscription download rate was provided, so no plan comparison was made.');
  }

  if (signal !== null) facts.push(`Windows reported a Wi-Fi signal strength of ${signal.toFixed(0)}%.`);
  if (overview?.status === 'reachable') facts.push('The separate basic-connectivity check reached its test destinations.');
  if (overview?.status === 'attention' || overview?.status === 'unverified') {
    facts.push('The separate basic-connectivity check did not confirm access to every test destination.');
  }

  let next;
  if (signal !== null && signal < 40) {
    next = 'Windows reports weak Wi-Fi signal. Repeat near the router or on Ethernet; compare the actual measurements before identifying the limiting connection.';
  } else if (percent !== null && percent < 80) {
    next = 'This test measured less than 80% of your entered plan. Pause other downloads and compare over Ethernet on the same computer. Repeat before reporting persistent low speed to your ISP.';
  } else {
    next = 'This measurement does not identify why a particular website, game or application is slow. Compare the affected service or repeat on Ethernet.';
  }

  return {
    headline: percent === null ? 'Your download speed has been measured' : `Measured download: ${percent.toFixed(0)}% of your entered plan`,
    facts, next,
    caution: 'A short test measures performance to Cloudflare, not every website. It does not identify a fault location by itself.',
  };
}

/** Only name Wi-Fi or Ethernet when the Windows default-route adapter name identifies it. */
export function routeType(overview) {
  const name = overview?.interface;
  if (typeof name !== 'string') return 'unverified';
  if (/\bwi[ -]?fi\b|\bwireless\b|\bwlan\b/i.test(name)) return 'wifi';
  if (/\bethernet\b|\bwired\b|\blocal area connection\b/i.test(name)) return 'ethernet';
  return 'unverified';
}

export function compareConnectionSpeeds(first, second, firstOverview, secondOverview) {
  const before = first?.download_mbps;
  const after = second?.download_mbps;
  if (!validRate(before) || !validRate(after)) {
    throw new Error('Two completed download measurements are required.');
  }

  const delta = after - before;
  const changePct = before > 0 ? 100 * delta / before : null;
  const format = n => n.toFixed(1);
  const difference = `${format(Math.abs(delta))} Mbps`;
  const adapterNamesMatch = routeType(firstOverview) === 'wifi' && routeType(secondOverview) === 'ethernet';
  const same = Math.abs(delta) < 0.05;
  const headline = same
    ? 'Both tests measured the same download speed to one decimal place'
    : `The second test measured ${difference} ${delta > 0 ? 'faster' : 'slower'}`;

  const facts = [
    `First test: ${format(before)} Mbps (Windows adapter: ${firstOverview?.interface || 'unavailable'}).`,
    `Second test: ${format(after)} Mbps (Windows adapter: ${secondOverview?.interface || 'unavailable'}).`,
    changePct === null ? 'Percentage change cannot be calculated from a zero baseline.' : `Difference relative to the first reading: ${Math.abs(changePct).toFixed(0)}% ${delta >= 0 ? 'higher' : 'lower'}.`,
    adapterNamesMatch
      ? 'Windows labelled the preferred adapter Wi-Fi after the first test and Ethernet after the second test.'
      : 'Windows adapter names did not establish a Wi-Fi-to-Ethernet switch.',
  ];

  let next;
  if (!adapterNamesMatch) {
    next = 'Check which adapter Windows is using. To investigate Wi-Fi, first test on Wi-Fi, then use Ethernet on the same computer and router. Re-run the comparison.';
  } else if (delta >= Math.max(3, before * 0.25)) {
    next = 'Ethernet measured faster in these runs. Repeat each test once with other downloads paused. If the difference repeats, inspect the Wi-Fi link, signal, interference and wireless adapter.';
  } else if (-delta >= Math.max(3, before * 0.25)) {
    next = 'Ethernet measured slower in these runs. Verify the cable and Ethernet link speed, then repeat both tests before assigning a cause.';
  } else {
    next = 'These two measurements do not show a large Wi-Fi-to-Ethernet difference using this comparison threshold. Repeat during the slowdown, then inspect the affected application or internet plan.';
  }

  return {
    headline, facts, next, adapterNamesMatch,
    caution: 'Two short tests do not prove a device or ISP fault. Adapter names are not packet-path verification. Compare on the same router and plan, with other downloads paused.',
  };
}
