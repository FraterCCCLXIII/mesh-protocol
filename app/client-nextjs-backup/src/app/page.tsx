"use client";

import { useEffect, useState } from "react";
import { getStoredUser, getStoredToken } from "@/lib/mesh";
import { Feed } from "@/components/feed";
import { Sidebar } from "@/components/sidebar";
import { AuthPage } from "@/components/auth-page";

export default function Home() {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const token = getStoredToken();
    const user = getStoredUser();
    setIsAuthenticated(!!token && !!user);
    setIsLoading(false);
  }, []);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthPage onSuccess={() => setIsAuthenticated(true)} />;
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto flex">
        <Sidebar />
        <main className="flex-1 border-x border-border min-h-screen">
          <Feed />
        </main>
        <aside className="w-80 p-4 hidden lg:block">
          <div className="sticky top-4">
            <div className="rounded-lg border bg-card p-4">
              <h3 className="font-semibold mb-2">About MESH</h3>
              <p className="text-sm text-muted-foreground">
                A decentralized social protocol with self-sovereign identity, 
                end-to-end encryption, and verifiable feeds.
              </p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
