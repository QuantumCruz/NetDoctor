
/** Interpret existing website diagnostics. No network calls. */
export function interpretWebsite(report, otherDevice = 'unknown') {
  const website = report?.website;

  if (!website || typeof website !== 'object') {
    throw new Error('A completed website diagnostic report is required.');
  }

  const code = Number.isInteger(website.http_status)
    ? website.http_status
    : null;

  const general = Array.isArray(report.steps)
    ? report.steps.find(step => step.key === 'internet')
    : null;

  let headline;
  let finding;
  let next = website.next_step ||
    'Open the same address in a browser and compare it on another network.';

  if (code !== null && website.stage === 'complete') {
    headline = `Confirmed: the website returned HTTP ${code}`;

    if (code >= 100 && code < 200) {
      finding =
        'The website returned an interim HTTP status. ' +
        'A final response to this diagnostic request was not observed.';
      next = 'Open the website normally in a browser, or repeat the check later.';
    } else if (code === 405 || code === 501) {
      finding =
        'The HTTPS server responded but did not support the HEAD request ' +
        'used by NetDoctor. This is not proof that the website fails in a browser.';
      next =
        'Open the website normally in a browser. ' +
        'NetDoctor does not send a full page request.';
    } else if (code >= 200 && code < 300) {
      finding =
        'The HTTPS connection succeeded and the site answered a metadata-only ' +
        'request. This does not verify that a full page loads in your browser.';
      next =
        'Try the exact address in your browser. ' +
        'If it fails there, compare another browser or device.';
    } else if (code >= 300 && code < 400) {
      finding =
        'The site replied with a redirect. NetDoctor did not follow ' +
        'the redirect to its destination.';
      next =
        'Open the address in your browser to check whether the ' +
        'redirected page loads.';
    } else if (code === 401 || code === 403) {
      finding =
        'The HTTPS server answered, but it rejected this request with ' +
        'an access status. This does not prove the website is offline.';
      next =
        'Open it in your browser and check whether login or website ' +
        'protection is involved.';
    } else if (code === 404) {
      finding =
        'The website replied that this address or path was not found ' +
        'for the HEAD request. Its HTTPS service was reachable.';
      next =
        'Check the exact address, especially the path after the domain name.';
    } else if (code === 429) {
      finding =
        'The website replied that requests are being rate-limited. ' +
        'The HTTPS service was reachable.';
      next =
        'Wait before trying again. Avoid repeatedly sending diagnostic requests.';
    } else if (code >= 500) {
      finding =
        'An HTTPS service responded with a server-error status. ' +
        'This alone does not establish which service or network component caused it.';
      next =
        'Try the exact page in a browser and on another network; ' +
        'record the HTTP status if the error repeats.';
    } else {
      finding =
        'An HTTPS service returned a response to the diagnostic request. ' +
        'The code does not establish whether the full page works.';
    }
  } else {
    switch (website.stage) {
      case 'dns':
        headline = 'Website name lookup did not return a usable public address';
        finding = website.explanation ||
          'No usable public address was found for the website.';
        next =
          'Check the spelling, then compare this exact site on another device. ' +
          'Do not change DNS settings based on one failed lookup.';
        break;

      case 'tcp':
        headline = 'The connection to this website did not complete';
        finding = website.explanation ||
          'The TCP connection could not be completed during this test.';
        next =
          'Try the same address again and compare it on another network.';
        break;

      case 'tls':
        headline = website.headline === 'Website certificate could not be verified'
          ? 'The website certificate could not be verified'
          : 'The secure connection to this website did not complete';
        finding = website.explanation ||
          'The secure HTTPS setup failed during this test.';
        next = website.next_step ||
          'Check the Windows clock and compare the site in your browser.';
        break;

      case 'http':
        headline =
          'HTTPS connected, but the website did not give a usable HEAD response';
        finding = website.explanation ||
          'The diagnostic request did not produce a usable HTTP response.';
        next =
          'Open the website in your browser. ' +
          'Some websites do not handle HEAD requests normally.';
        break;

      default:
        headline = 'The website check did not finish';
        finding = website.explanation ||
          'The website check returned no conclusive result.';
    }
  }

  if (otherDevice === 'works') {
    next =
      'You reported that the site works on another device using the same Wi-Fi. ' +
      'On this computer, compare browsers, the exact URL, VPN/proxy settings ' +
      'and browser extensions before changing router or ISP settings.';
  } else if (otherDevice === 'fails') {
    next =
      'You reported the site also fails on another device using the same Wi-Fi. ' +
      'Check it using mobile data or another network. That comparison separates ' +
      'a shared-network problem from a website-side problem.';
  }

  const generalFinding = general?.status === 'confirmed'
    ? 'Both general public HTTPS checks succeeded during this diagnosis.'
    : general?.status === 'mixed'
      ? 'Only some general public HTTPS checks connected during this diagnosis.'
      : general?.status === 'inconclusive'
        ? 'General public HTTPS checks did not establish connectivity during this diagnosis.'
        : 'General public HTTPS connectivity was not established by this report.';

  return {
    headline,
    finding,
    next,
    generalFinding,
    details: {
      target: website.target || null,
      httpStatus: code,
      stage: website.stage || 'unknown',
      addressFamily: website.address_family || null,
      measuredAt: website.tested_at || report.tested_at || null,
    },
    limitation:
      'NetDoctor sends an HTTPS HEAD request, not a browser page load. ' +
      'It does not follow redirects, download page content or prove who caused a failure.',
  };
}
