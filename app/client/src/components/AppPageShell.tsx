import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";

/**
 * Standard desktop layout: in-app {@link Sidebar} + bordered main column.
 * Global {@link Layout} still provides mobile header / bottom nav / FAB.
 */
export function AppPageShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto flex max-w-6xl">
        <Sidebar />
        <main className="min-h-screen w-full min-w-0 flex-1 border-x border-border">
          {children}
        </main>
      </div>
    </div>
  );
}
