/**
 * Type declarations for htmx.org
 *
 * htmx.org doesn't ship with official TypeScript declarations.
 * This minimal declaration allows us to import and use htmx in TypeScript/Astro files.
 */

declare module 'htmx.org' {
  interface HtmxApi {
    process(element: HTMLElement | Document): void;
    // Add other htmx methods as needed
  }

  const htmx: HtmxApi;
  export default htmx;
}

// Extend Window interface to include htmx
declare global {
  interface Window {
    htmx: {
      process(element: HTMLElement | Document): void;
    };
  }
}
