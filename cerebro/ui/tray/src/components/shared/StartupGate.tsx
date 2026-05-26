import type { ReactNode } from "react";

interface StartupGateProps {
  children: ReactNode;
}

/** Passthrough — backend boot is controlled via header Turn on/off, not a blocking gate. */
export default function StartupGate({ children }: StartupGateProps) {
  return <>{children}</>;
}
