
import './confirmInPage.css';

let activeConfirmation = false;
let nextId = 0;

function displayConfirmation({
  title = 'Confirm this action',
  message,
  confirmLabel = 'Continue',
  cancelLabel = 'Cancel',
} = {}) {
  return new Promise((resolve, reject) => {
    if (typeof message !== 'string' || !message.trim()) {
      reject(new Error('A confirmation message is required.'));
      return;
    }

    const previousFocus = document.activeElement;
    const dialog = document.createElement('dialog');
    const panel = document.createElement('div');
    const heading = document.createElement('h2');
    const description = document.createElement('p');
    const disclosure = document.createElement('div');
    const buttons = document.createElement('div');
    const cancel = document.createElement('button');
    const accept = document.createElement('button');

    const id = ++nextId;
    let settled = false;

    dialog.className = 'nd-consent-dialog';
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute(
      'aria-labelledby',
      `nd-consent-title-${id}`
    );
    dialog.setAttribute(
      'aria-describedby',
      `nd-consent-message-${id}`
    );

    panel.className = 'nd-consent-panel';

    disclosure.className = 'nd-consent-heading';
    disclosure.textContent = 'NETDOCTOR · YOUR PERMISSION';

    heading.id = `nd-consent-title-${id}`;
    heading.textContent = title;

    description.id = `nd-consent-message-${id}`;
    description.textContent = message;

    buttons.className = 'nd-consent-actions';

    cancel.type = 'button';
    cancel.className = 'nd-consent-cancel';
    cancel.textContent = cancelLabel;

    accept.type = 'button';
    accept.className = 'nd-consent-accept';
    accept.textContent = confirmLabel;

    function finish(approved) {
      if (settled) return;

      settled = true;

      if (dialog.open) {
        dialog.close();
      }

      dialog.remove();

      if (
        previousFocus &&
        typeof previousFocus.focus === 'function' &&
        previousFocus.isConnected
      ) {
        previousFocus.focus();
      }

      resolve(approved);
    }

    cancel.addEventListener('click', () => finish(false));
    accept.addEventListener('click', () => finish(true));

    dialog.addEventListener('cancel', event => {
      event.preventDefault();
      finish(false);
    });

    dialog.addEventListener('close', () => {
      finish(false);
    });

    dialog.addEventListener('click', event => {
      if (event.target === dialog) {
        finish(false);
      }
    });

    buttons.append(cancel, accept);
    panel.append(disclosure, heading, description, buttons);
    dialog.append(panel);
    document.body.append(dialog);

    try {
      if (typeof dialog.showModal !== 'function') {
        throw new Error(
          'The current WebView2 runtime does not support ' +
          'in-page confirmation dialogs.'
        );
      }

      dialog.showModal();
      cancel.focus();
    } catch (error) {
      dialog.remove();
      reject(error);
    }
  });
}

/**
 * Explicit, asynchronous, on-page user confirmation.
 * A second request is refused while a dialog is already open.
 *
 * Returns true only when the user selects the affirmative button.
 * Cancellation, Escape and backdrop clicks return false.
 */
export function confirmInPage(options) {
  // A second action cannot queue another dialog or share the first approval.
  if (activeConfirmation) return Promise.resolve(false);

  activeConfirmation = true;

  return displayConfirmation(options)
    .catch(error => {
      console.error('NetDoctor could not show the in-page dialog:', error);
      return false;
    })
    .finally(() => {
      activeConfirmation = false;
    });
}
