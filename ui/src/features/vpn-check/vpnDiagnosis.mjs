
/**
 * Compare two opt-in public-IP observations.
 * This does not test VPN encryption or GPS location.
 */

function validSample(report) {
  return (
    report &&
    typeof report.public_ip === 'string' &&
    report.public_ip.length > 0 &&
    ['IPv4', 'IPv6'].includes(report.ip_family)
  );
}

function countryCode(report) {
  const code = report?.country_code;

  return (
    typeof code === 'string' &&
    /^[A-Z]{2}$/.test(code)
  )
    ? code
    : null;
}

export function compareVpnExit(before, after) {
  if (!validSample(before) || !validSample(after)) {
    throw new Error(
      'Two valid public-IP reports are required.'
    );
  }

  const sameFamily =
    before.ip_family === after.ip_family;

  const ipChanged = sameFamily
    ? before.public_ip !== after.public_ip
    : null;

  const fromCode = countryCode(before);
  const toCode = countryCode(after);

  const countryChanged = fromCode && toCode
    ? fromCode !== toCode
    : null;

  let headline;
  let explanation;

  if (!sameFamily) {
    headline =
      'The lookups used different IP versions';

    explanation =
      'The first lookup used IPv4/IPv6 differently ' +
      'from the second. These addresses cannot ' +
      'establish a like-for-like change in your VPN exit.';
  } else if (ipChanged) {
    headline =
      'Confirmed: the public IP changed';

    explanation =
      'The HTTPS lookup observed a different public IP ' +
      'after you reported connecting the VPN. ' +
      'This confirms an exit-IP change for the tested ' +
      'request, not that every app uses the VPN.';
  } else {
    headline =
      'No public IP change detected';

    explanation =
      'Both HTTPS lookups observed the same public IP. ' +
      'This test did not verify a different VPN exit. ' +
      'A split tunnel or an unchanged exit address ' +
      'can explain the result.';
  }

  let location;

  if (countryChanged === true) {
    location =
      `IP-based country changed from ` +
      `${before.country || fromCode} to ` +
      `${after.country || toCode}.`;
  } else if (countryChanged === false) {
    location =
      `Both addresses geolocate to ` +
      `${after.country || toCode}.`;
  } else {
    location =
      'The service did not return enough country ' +
      'information to compare apparent locations.';
  }

  if (
    ipChanged === false &&
    countryChanged === true
  ) {
    location +=
      ' Because the IP did not change, differing ' +
      'geolocation labels do not establish a ' +
      'VPN exit change.';
  }

  return {
    headline,
    explanation,
    location,
    changed: ipChanged,
    countryChanged,

    next: !sameFamily
      ? (
          'Repeat both checks using the same IP version. ' +
          'IPv4 and IPv6 can follow different routes.'
        )
      : ipChanged
        ? (
            'Check DNS and IPv6 leak behaviour separately ' +
            'if you need stronger privacy verification.'
          )
        : (
            'Confirm the VPN is connected and retry. ' +
            'If split tunnelling is enabled, check whether ' +
            'NetDoctor uses the VPN route.'
          ),

    limitation:
      'IP geolocation is approximate. This test does ' +
      'not verify encryption, DNS/WebRTC leaks, all ' +
      'application routes or your physical location.',
  };
}
