/** Paths that own the viewport — static landing markup in index.html must hide. */
const APP_ROUTE_RE = /^\/(demo|tiles)(\/|$)|^\/snapshot(\/|$)/;

export function isAppRoute(pathname: string): boolean {
  return APP_ROUTE_RE.test(pathname);
}

export function syncSpaShell(pathname: string): void {
  document.body.classList.toggle("spa-app", isAppRoute(pathname));
}
