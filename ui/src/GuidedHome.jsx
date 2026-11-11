import { useEffect, useRef, useState } from 'react';
import {
  Activity, ChevronDown, CircleHelp, Cloud, Gauge,
  Gamepad2, Laptop2, MessageCircle,
  Signal, Stethoscope, Wrench,
} from 'lucide-react';

import InternetFaultFlow from './features/internet-fault/InternetFaultFlow.jsx';
import PortForwardingFlow from './features/port-forwarding/PortForwardingFlow.jsx';
import SlowInternetFlow from './features/slow-internet/SlowInternetFlow.jsx';
import DisconnectFlow from './features/disconnections/DisconnectFlow.jsx';
import WebsiteFlow from './features/website/WebsiteFlow.jsx';
import VpsFinderFlow from './features/vps-finder/VpsFinderFlow.jsx';
import VpnCheckFlow from './features/vpn-check/VpnCheckFlow.jsx';

import './guided-home.css';
import './unified-navigation.css';

const QUESTIONS = [
  ['internet', "What's wrong with my internet?"],
  ['port', 'Why is my port forwarding not working?'],
  ['slow', 'Why is my internet slow?'],
  ['disconnect', 'Why does my internet keep disconnecting?'],
  ['website', "Why won't a website open?"],
  ['vps', 'Which VPS location has the lowest latency?'],
  ['vpn', 'Is my VPN working?'],
];

const TOOLS = [
  ['dashboard', 'Overview', Gauge],
  ['diagnosis', 'Diagnosis', Stethoscope],
  ['activities', 'Activities', Gamepad2],
  ['stability', 'Stability', Signal],
  ['cloud', 'Cloud regions', Cloud],
  ['details', 'Network details', Laptop2],
];

/**
 * Determine whether navigating away would interrupt a foreground check.
 *
 * Guided flows already expose their busy state using aria-busy.
 * The Diagnosis tool uses the same attribute.
 *
 * Activities exposes temporary status messages while its refresh
 * or loaded-latency request is running.
 *
 * Other tools retain their operations independently, so they are
 * deliberately excluded from the navigation lock.
 */
function hasForegroundOperation(root, page, toolTab) {
  if (!root || page === 'questions') {
    return false;
  }

  if (page === 'tool') {
    const activeTool = root.querySelector(
      '.nd-page-enter'
    );

    if (!activeTool) {
      return false;
    }

    if (toolTab === 'diagnosis') {
      return Boolean(
        activeTool.querySelector('[aria-busy="true"]')
      );
    }

    if (toolTab === 'activities') {
      return Boolean(
        activeTool.querySelector('[role="status"]')
      );
    }

    return false;
  }

  return Boolean(
    root.querySelector(
      '.guided-main [aria-busy="true"]'
    )
  );
}

function Questions({ onChoose }) {
  return (
    <main className="guided-main">
      <header className="guided-header">
        <div>
          <p className="guided-eyebrow">
            NETWORK HELP, MADE SIMPLE
          </p>

          <h1>Ask NetDoctor</h1>

          <p>
            Select what you want to understand
            about your connection.
          </p>
        </div>
      </header>

      <section
        className="guided-chat"
        aria-label="Troubleshooting questions"
      >
        <div className="guided-message">
          <span className="guided-avatar">
            <Activity size={18} />
          </span>

          <div className="guided-bubble">
            <strong>Hello! I'm NetDoctor.</strong>

            <p>
              What's going wrong with your network?
            </p>
          </div>
        </div>

        {QUESTIONS.map(([id, question]) => (
          <button
            key={id}
            type="button"
            className="guided-question"
            onClick={() => onChoose(id)}
          >
            <CircleHelp size={19} />
            <span>{question}</span>
          </button>
        ))}
      </section>
    </main>
  );
}

export default function GuidedHome({ ToolsApp }) {
  const [page, setPage] = useState('questions');
  const [toolsOpen, setToolsOpen] = useState(false);
  const [toolTab, setToolTab] = useState('dashboard');
  const [toolsMounted, setToolsMounted] = useState(false);
  const [navigationLocked, setNavigationLocked] = useState(false);

  const viewport = useRef(null);
  const isTool = page === 'tool';

  /*
   * Recheck the actual foreground operation before navigation.
   * This protects navigation even before the observer has updated
   * the visible disabled state.
   */
  function isNavigationBlocked() {
    return hasForegroundOperation(
      viewport.current,
      page,
      toolTab
    );
  }

  function openTool(tab) {
    if (isNavigationBlocked()) {
      return;
    }

    setToolTab(tab);
    setToolsMounted(true);
    setToolsOpen(true);
    setPage('tool');
  }

  function openQuestion(id) {
    if (isNavigationBlocked()) {
      return;
    }

    setPage(id);
  }

  function back() {
    if (isNavigationBlocked()) {
      return;
    }

    setPage('questions');
  }

  function toggleTools() {
    if (isNavigationBlocked()) {
      return;
    }

    setToolsOpen(value => !value);
  }

  /*
   * Observe existing accessibility states instead of changing the
   * network engines or requiring every guided flow to implement
   * a separate navigation callback.
   *
   * Both state updates and added/removed status elements are
   * detected, so navigation unlocks when a check finishes.
   */
  useEffect(() => {
    const root = viewport.current;

    if (!root) {
      return undefined;
    }

    function refreshNavigationLock() {
      const locked = hasForegroundOperation(
        root,
        page,
        toolTab
      );

      setNavigationLocked(previous =>
        previous === locked ? previous : locked
      );
    }

    refreshNavigationLock();

    const observer = new MutationObserver(
      refreshNavigationLock
    );

    observer.observe(root, {
      attributes: true,
      attributeFilter: ['aria-busy'],
      childList: true,
      subtree: true,
    });

    return () => {
      observer.disconnect();
    };
  }, [page, toolTab]);

  useEffect(() => {
    if (viewport.current) {
      viewport.current.scrollTop = 0;
    }
  }, [page, toolTab]);

  const navigationMessage = navigationLocked
    ? 'A network check is in progress. Navigation will be available when it finishes.'
    : undefined;

  return (
    <div className="guided-shell">
      <aside
        className="guided-sidebar"
        aria-label="Primary navigation"
      >
        <div className="guided-brand">
          <span className="guided-brand-mark">
            <Activity size={22} />
          </span>

          <strong>
            Net<span>Doctor</span>
          </strong>
        </div>

        <p className="guided-sidebar-caption">
          WORKSPACE
        </p>

        <button
          type="button"
          className={`guided-nav ${
            !isTool ? 'guided-nav-active' : ''
          }`}
          aria-current={!isTool ? 'page' : undefined}
          disabled={navigationLocked}
          title={navigationMessage}
          onClick={back}
          style={{
            opacity: navigationLocked ? 0.5 : undefined,
            cursor: navigationLocked ? 'not-allowed' : undefined,
          }}
        >
          <MessageCircle size={19} />
          <span>Ask NetDoctor</span>
        </button>

        <button
          type="button"
          className={`guided-nav guided-nav-parent ${
            isTool ? 'guided-nav-parent-active' : ''
          }`}
          aria-expanded={toolsOpen}
          aria-controls="guided-tools-list"
          disabled={navigationLocked}
          title={navigationMessage}
          onClick={toggleTools}
          style={{
            opacity: navigationLocked ? 0.5 : undefined,
            cursor: navigationLocked ? 'not-allowed' : undefined,
          }}
        >
          <Wrench size={19} />
          <span>Explore tools</span>

          <ChevronDown
            className={`guided-chevron ${
              toolsOpen ? 'guided-chevron-open' : ''
            }`}
            size={16}
          />
        </button>

        {toolsOpen && (
          <nav
            id="guided-tools-list"
            className="guided-subnav"
            aria-label="NetDoctor tools"
          >
            {TOOLS.map(([id, label, Icon]) => (
              <button
                key={id}
                type="button"
                className={`guided-subnav-item ${
                  isTool && toolTab === id
                    ? 'guided-subnav-active'
                    : ''
                }`}
                aria-current={
                  isTool && toolTab === id
                    ? 'page'
                    : undefined
                }
                disabled={navigationLocked}
                title={navigationMessage}
                onClick={() => openTool(id)}
                style={{
                  opacity: navigationLocked ? 0.5 : undefined,
                  cursor: navigationLocked ? 'not-allowed' : undefined,
                }}
              >
                <Icon size={17} />
                <span>{label}</span>
              </button>
            ))}
          </nav>
        )}

        {navigationLocked && (
          <div
            role="status"
            aria-live="polite"
            style={{
              marginTop: 18,
              padding: '12px 13px',
              borderRadius: 10,
              border: '1px solid #37506e',
              background: '#12223a',
              color: '#d4e5f4',
              fontSize: 12,
              lineHeight: 1.6,
            }}
          >
            <strong
              style={{
                display: 'block',
                color: '#63e8cb',
                marginBottom: 4,
              }}
            >
              Network check in progress
            </strong>

            Please stay on this page until the check finishes.
            Navigation will unlock automatically.
          </div>
        )}

        <p className="guided-sidebar-footer">
          Local Windows app
        </p>
      </aside>

      <div
        className="guided-viewport"
        ref={viewport}
      >
        {page === 'questions' && (
          <Questions onChoose={openQuestion} />
        )}

        {page === 'internet' && (
          <InternetFaultFlow onBack={back} />
        )}

        {page === 'port' && (
          <PortForwardingFlow
            autoStart
            onBack={back}
            onExploreTools={() => openTool('dashboard')}
          />
        )}

        {page === 'slow' && (
          <SlowInternetFlow onBack={back} />
        )}

        {page === 'disconnect' && (
          <DisconnectFlow onBack={back} />
        )}

        {page === 'website' && (
          <WebsiteFlow onBack={back} />
        )}

        {page === 'vps' && (
          <VpsFinderFlow onBack={back} />
        )}

        {page === 'vpn' && (
          <VpnCheckFlow onBack={back} />
        )}

        {toolsMounted && (
          <div
            className="guided-tool-host"
            hidden={!isTool}
          >
            <ToolsApp
              activeTab={toolTab}
              onNavigate={openTool}
            />
          </div>
        )}
      </div>
    </div>
  );
}