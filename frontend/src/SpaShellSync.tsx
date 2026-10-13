import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { syncSpaShell } from "./spaShell";

/** Keeps ``body.spa-app`` aligned with the active React Router path. */
export default function SpaShellSync() {
  const { pathname } = useLocation();
  useEffect(() => {
    syncSpaShell(pathname);
  }, [pathname]);
  return null;
}
