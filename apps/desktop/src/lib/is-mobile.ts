// True when the renderer is running inside the mobile WebView shell. The flag
// is set by apps/mobile (see bundled-renderer-html injection) before React
// mounts, so this is safe to call at module top level. Defaults to false in
// every other context (Electron desktop, vitest, SSR).
export function isMobile(): boolean {
  return (
    typeof window !== 'undefined' &&
    Boolean((window as { __HERMES_MOBILE_STANDALONE__?: boolean }).__HERMES_MOBILE_STANDALONE__)
  )
}
