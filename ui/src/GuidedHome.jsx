
import { useEffect, useRef, useState } from 'react';
import {
  Activity, ChevronDown, CircleHelp, Cloud, Gauge,
  Gamepad2, Laptop2, MessageCircle,
  Signal, Stethoscope, Wrench,
} from 'lucide-react';

import PortForwardingFlow from './features/port-forwarding/PortForwardingFlow.jsx';
import SlowInternetFlow from './features/slow-internet/SlowInternetFlow.jsx';
import DisconnectFlow from './features/disconnections/DisconnectFlow.jsx';
import WebsiteFlow from './features/website/WebsiteFlow.jsx';
import VpsFinderFlow from './features/vps-finder/VpsFinderFlow.jsx';
import VpnCheckFlow from './features/vpn-check/VpnCheckFlow.jsx';
import './guided-home.css';
import './unified-navigation.css';

const QUESTIONS = [
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

  const viewport = useRef(null);
  const isTool = page === 'tool';

  function openTool(tab) {
    setToolTab(tab);
    setToolsMounted(true);
    setToolsOpen(true);
    setPage('tool');
  }

  function openQuestion(id) {
    setPage(id);
  }

  useEffect(() => {
    if (viewport.current) {
      viewport.current.scrollTop = 0;
    }
  }, [page, toolTab]);

  const back = () => setPage('questions');

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
          onClick={back}
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
          onClick={() => setToolsOpen(value => !value)}
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
                onClick={() => openTool(id)}
              >
                <Icon size={17} />
                <span>{label}</span>
              </button>
            ))}
          </nav>
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
