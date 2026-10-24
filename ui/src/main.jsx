
const mount = document.getElementById('root');

function showStartupError(reason) {
  const message =
    reason instanceof Error
      ? `${reason.name}: ${reason.message}`
      : String(reason || 'Unknown JavaScript error');

  console.error('NetDoctor UI failed:', reason);

  if (!mount) return;

  mount.replaceChildren();

  const panel = document.createElement('section');
  panel.style.cssText = `
    max-width: 780px;
    margin: 8vh auto;
    padding: 28px;
    border: 1px solid #925a53;
    border-radius: 14px;
    background: #172337;
    color: #eaf1ff;
    font: 16px system-ui;
    line-height: 1.6;
  `;

  const heading = document.createElement('h1');
  heading.textContent = 'NetDoctor could not start the dashboard';

  const explanation = document.createElement('p');
  explanation.textContent =
    'The window opened, but the dashboard encountered an error. ' +
    'The message below identifies what needs fixing.';

  const detail = document.createElement('pre');
  detail.style.cssText = `
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    padding: 14px;
    background: #0c1423;
    color: #ffd7ac;
    border-radius: 8px;
  `;
  detail.textContent = message;

  panel.append(heading, explanation, detail);
  mount.append(panel);
}

window.addEventListener('error', event => {
  showStartupError(event.error || event.message);
});

window.addEventListener('unhandledrejection', event => {
  showStartupError(event.reason);
});

if (!mount) {
  console.error(
    'NetDoctor is missing the #root element in index.html'
  );
} else {
  Promise.all([
    import('react'),
    import('react-dom/client'),
    import('./App.jsx'),
    import('./styles.css'),
  ])
    .then(([ReactModule, DOMModule, AppModule]) => {
      const React = ReactModule.default || ReactModule;
      const App = AppModule.default;

      if (typeof App !== 'function') {
        throw new Error(
          'App.jsx did not export a React component as default.'
        );
      }

      class StartupBoundary extends React.Component {
        constructor(props) {
          super(props);
          this.state = { error: null };
        }

        static getDerivedStateFromError(error) {
          return { error };
        }

        componentDidCatch(error) {
          console.error(
            'NetDoctor React render error:',
            error
          );
        }

        render() {
          if (this.state.error) {
            return React.createElement(
              'section',
              {
                style: {
                  margin: '8vh auto',
                  padding: 28,
                  maxWidth: 780,
                  color: '#fff',
                },
              },
              React.createElement(
                'h1',
                null,
                'NetDoctor dashboard error'
              ),
              React.createElement(
                'pre',
                {
                  style: {
                    whiteSpace: 'pre-wrap',
                    color: '#ffd7ac',
                  },
                },
                String(this.state.error)
              )
            );
          }

          return this.props.children;
        }
      }

      DOMModule.createRoot(mount).render(
        React.createElement(
          StartupBoundary,
          null,
          React.createElement(
            React.StrictMode,
            null,
            React.createElement(App)
          )
        )
      );
    })
    .catch(showStartupError);
}
