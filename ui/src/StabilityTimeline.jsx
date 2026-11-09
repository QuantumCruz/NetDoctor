
import { Fragment, useMemo, useState } from 'react';
import { prepareStabilityTimeline } from './stabilityTimeline.mjs';

const COLORS = {
  connected: '#63e8cb',
  notConnected: '#ef8f8f',
  unanswered: '#f1c67a',
  unmeasured: '#70839d',
};

const LANES = [
  { key: 'first_ok', name: 'Cloudflare 1.1.1.1' },
  { key: 'second_ok', name: 'Google 8.8.8.8' },
  { key: 'gateway_reply', name: 'Gateway ping' },
];

function clockTime(ms) {
  return new Date(ms).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function outcome(value, gateway = false) {
  if (gateway) {
    return value === true
      ? 'ICMP reply received'
      : value === false
        ? 'No ICMP reply (not proof of router failure)'
        : 'Not measured';
  }

  return value
    ? 'TCP connected'
    : 'TCP connection not confirmed';
}

function Legend({ color, children }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7,
      }}
    >
      <span
        aria-hidden="true"
        style={{
          display: 'inline-block',
          width: 10,
          height: 10,
          borderRadius: 3,
          background: color,
          flexShrink: 0,
        }}
      />
      {children}
    </span>
  );
}

export default function StabilityTimeline({
  samples = [],
  intervalSeconds = 10,
}) {
  const [range, setRange] = useState('30');
  const [selectedId, setSelectedId] = useState(null);

  const timeline = useMemo(
    () => prepareStabilityTimeline(
      samples,
      intervalSeconds,
      range === 'all' ? null : Number(range)
    ),
    [samples, intervalSeconds, range]
  );

  const {
    points,
    gaps,
    ticks,
    domainMin,
    domainMax,
    availableCount,
  } = timeline;

  const chosen =
    points.find(
      point => point.originalIndex === selectedId
    ) ?? points.at(-1);

  const percent = time =>
    ((time - domainMin) / (domainMax - domainMin)) * 100;

  const markerPercent = Math.min(
    1.7,
    Math.max(0.35, 85 / Math.max(points.length, 60))
  );

  const visibleCount = points.length;
  const savedCount = availableCount;

  const checkNoun = savedCount === 1 ? 'check' : 'checks';

  const rangeDescription =
    range === 'all'
      ? 'All available recorded history'
      : `Last ${range} minutes before the newest check`;

  let recordedPeriod = '';

  if (visibleCount === 1) {
    recordedPeriod = new Date(
      points[0].timeMs
    ).toLocaleString();
  } else if (visibleCount > 1) {
    recordedPeriod =
      `${new Date(points[0].timeMs).toLocaleDateString()} · ` +
      `${clockTime(points[0].timeMs)}–` +
      `${clockTime(points.at(-1).timeMs)}`;
  }

  return (
    <section
      aria-label="Connection timeline"
      style={{ minWidth: 0 }}
    >
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <div>
          <h3
            style={{
              margin: 0,
              fontSize: 19,
            }}
          >
            Connection timeline
          </h3>

          <p
            style={{
              margin: '5px 0 0',
              color: '#aebfd5',
              fontSize: 13,
            }}
          >
            Actual recorded connection checks,
            not estimated uptime.
          </p>
        </div>

        <label
          style={{
            color: '#bbcee4',
            fontSize: 13,
          }}
        >
          View{' '}

          <select
            aria-label="Timeline time range"
            value={range}
            onChange={event => {
              setRange(event.target.value);
              setSelectedId(null);
            }}
            style={{
              marginLeft: 8,
              padding: '8px 10px',
              borderRadius: 9,
              color: '#eaf1ff',
              background: '#0b1528',
              border: '1px solid #35506f',
            }}
          >
            <option value="15">
              Last 15 minutes
            </option>

            <option value="30">
              Last 30 minutes
            </option>

            <option value="all">
              All available (up to 120)
            </option>
          </select>
        </label>
      </div>

      {visibleCount === 0 ? (
        <p
          style={{
            padding: '22px 12px',
            textAlign: 'center',
            color: '#9bb1cb',
          }}
        >
          No checks recorded for this connection yet.
          Start monitoring to build a timeline.
        </p>
      ) : (
        <>
          <p
            style={{
              color: '#aebfd5',
              fontSize: 12,
              margin: '12px 0',
              lineHeight: 1.7,
            }}
          >
            <strong>
              Showing {visibleCount} of {savedCount} saved {checkNoun}
            </strong>
            {' · '}
            {rangeDescription}
            {' · '}
            {recordedPeriod}
            {' · '}
            {gaps.length} unobserved{' '}
            {gaps.length === 1 ? 'gap' : 'gaps'}
          </p>

          <div
            role="img"
            aria-label={
              `Three-lane history showing ${visibleCount} ` +
              `of ${savedCount} saved checks. ` +
              `${gaps.length} gaps without observations. ` +
              'Use the selector below for individual details.'
            }
            style={{
              display: 'grid',
              gridTemplateColumns:
                'minmax(110px, 154px) minmax(0, 1fr)',
              alignItems: 'center',
              gap: '10px 12px',
              minWidth: 0,
            }}
          >
            {LANES.map((lane, laneIndex) => (
              <Fragment key={lane.key}>
                <span
                  style={{
                    color: '#c2d2e4',
                    fontSize: 13,
                  }}
                >
                  {lane.name}
                </span>

                <div
                  style={{
                    position: 'relative',
                    minWidth: 0,
                    width: '100%',
                    height: 27,
                    background:
                      laneIndex % 2
                        ? '#17283f'
                        : '#122239',
                    borderRadius: 6,
                    overflow: 'hidden',
                  }}
                >
                  {[0, 1, 2, 3, 4].map(tick => (
                    <span
                      key={tick}
                      aria-hidden="true"
                      style={{
                        position: 'absolute',
                        left: `${tick * 25}%`,
                        top: 0,
                        bottom: 0,
                        borderLeft: '1px dashed #31455f',
                      }}
                    />
                  ))}

                  {gaps.map((gap, index) => (
                    <span
                      key={index}
                      aria-hidden="true"
                      style={{
                        position: 'absolute',
                        top: 0,
                        bottom: 0,
                        left: `${percent(gap.fromMs)}%`,
                        width: `${
                          percent(gap.toMs) -
                          percent(gap.fromMs)
                        }%`,
                        background:
                          'rgba(144, 165, 194, 0.13)',
                        borderLeft:
                          '1px dashed #667e9e',
                        borderRight:
                          '1px dashed #667e9e',
                      }}
                    />
                  ))}

                  {points.map(point => {
                    const value = point[lane.key];

                    const color =
                      laneIndex === 2
                        ? value === true
                          ? COLORS.connected
                          : value === false
                            ? COLORS.unanswered
                            : COLORS.unmeasured
                        : value
                          ? COLORS.connected
                          : COLORS.notConnected;

                    return (
                      <span
                        key={
                          `${point.timeMs}-` +
                          `${point.originalIndex}`
                        }
                        title={
                          `${clockTime(point.timeMs)} — ` +
                          outcome(value, laneIndex === 2)
                        }
                        style={{
                          position: 'absolute',
                          top: 5,
                          bottom: 5,
                          left: `${
                            Math.max(
                              1.5,
                              Math.min(
                                98.5,
                                percent(point.timeMs)
                              )
                            )
                          }%`,
                          transform: 'translateX(-50%)',
                          width: `${markerPercent}%`,
                          minWidth: 3,
                          maxWidth: 11,
                          borderRadius: 3,
                          background: color,
                        }}
                      />
                    );
                  })}
                </div>
              </Fragment>
            ))}

            <span />

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                gap: 6,
                color: '#a4b9d1',
                fontSize: 12,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {[ticks[0], ticks[2], ticks[4]].map(
                (time, index) => (
                  <span key={index}>
                    {clockTime(time)}
                  </span>
                )
              )}
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '8px 17px',
              marginTop: 13,
              color: '#bacbe0',
              fontSize: 12,
            }}
          >
            <Legend color={COLORS.connected}>
              Connected / replied
            </Legend>

            <Legend color={COLORS.notConnected}>
              TCP not confirmed
            </Legend>

            <Legend color={COLORS.unanswered}>
              Gateway unanswered
            </Legend>

            <Legend color={COLORS.unmeasured}>
              Not measured
            </Legend>
          </div>

          <details
            style={{
              marginTop: 17,
              padding: '12px 16px',
              borderRadius: 11,
              border: '1px solid #2b405b',
            }}
          >
            <summary
              style={{
                cursor: 'pointer',
                color: '#cce0f3',
                fontWeight: 600,
              }}
            >
              Inspect an individual check
            </summary>

            <label
              style={{
                display: 'block',
                color: '#adc0d7',
                fontSize: 13,
                marginTop: 13,
              }}
            >
              Recorded at

              <select
                aria-label="Select recorded check"
                value={chosen?.originalIndex ?? ''}
                onChange={event =>
                  setSelectedId(
                    Number(event.target.value)
                  )
                }
                style={{
                  display: 'block',
                  marginTop: 7,
                  padding: '9px 11px',
                  background: '#0b1528',
                  color: '#eff6ff',
                  border: '1px solid #35506f',
                  borderRadius: 8,
                  maxWidth: '100%',
                }}
              >
                {[...points].reverse().map(point => (
                  <option
                    key={point.originalIndex}
                    value={point.originalIndex}
                  >
                    {new Date(
                      point.timeMs
                    ).toLocaleString()}
                  </option>
                ))}
              </select>
            </label>

            {chosen && (
              <div
                style={{
                  color: '#c8d8e9',
                  fontSize: 13,
                  lineHeight: 1.8,
                  marginTop: 9,
                }}
              >
                <div>
                  Cloudflare:{' '}
                  {outcome(chosen.first_ok)}
                </div>

                <div>
                  Google:{' '}
                  {outcome(chosen.second_ok)}
                </div>

                <div>
                  Gateway:{' '}
                  {outcome(
                    chosen.gateway_reply,
                    true
                  )}
                </div>
              </div>
            )}
          </details>

          <p
            className="disclaimer"
            style={{ marginTop: 12 }}
          >
            Blank time gaps mean no saved observation,
            not confirmed downtime. An unanswered
            gateway ping does not establish router
            failure. Per-check latency is not measured.
          </p>
        </>
      )}
    </section>
  );
}
