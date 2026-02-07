/**
 * React Island Entry Point: SignalChainBuilder
 *
 * STORY-010: Configure SignalChainBuilder React Island
 *
 * This file provides a standalone mount function for loading the SignalChainBuilder
 * React component in non-Astro pages (Jinja2 SSR templates).
 *
 * Usage in HTML:
 *   <div id="signal-chain-builder-root"></div>
 *   <script src="/static/islands/signal-chain-builder.js"></script>
 *   <script>
 *     window.SignalChainBuilder.mount('signal-chain-builder-root');
 *   </script>
 */
import { createRoot } from 'react-dom/client';
import { SignalChainBuilder } from '@/components/SignalChain';
import '@/styles/global.css';

/**
 * Mount the SignalChainBuilder component to a DOM element.
 *
 * @param elementId - The ID of the DOM element to mount to
 * @param props - Optional props to pass to the SignalChainBuilder
 */
function mount(
  elementId: string,
  props?: {
    maxBlocksPerStage?: number;
    className?: string;
  }
): void {
  const container = document.getElementById(elementId);
  if (!container) {
    console.error(
      `SignalChainBuilder: Could not find element with id "${elementId}"`
    );
    return;
  }

  const root = createRoot(container);
  root.render(<SignalChainBuilder {...props} />);
}

// Export to global window object for use in non-module scripts
declare global {
  interface Window {
    SignalChainBuilder: {
      mount: typeof mount;
    };
  }
}

window.SignalChainBuilder = { mount };

export { mount };
