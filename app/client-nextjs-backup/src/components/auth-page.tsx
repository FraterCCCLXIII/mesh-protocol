"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { register, login, getStoredKeys } from "@/lib/mesh";

interface AuthPageProps {
  onSuccess: () => void;
}

export function AuthPage({ onSuccess }: AuthPageProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [handle, setHandle] = useState("");
  const [name, setName] = useState("");
  const [bio, setBio] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "register") {
        if (!handle || !name) {
          throw new Error("Handle and name are required");
        }
        await register(handle, name, bio);
      } else {
        const keys = getStoredKeys();
        if (!keys) {
          throw new Error("No keys found. Please register first.");
        }
        await login();
      }
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const hasExistingKeys = typeof window !== "undefined" && getStoredKeys() !== null;

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-3xl font-bold tracking-tight">MESH</CardTitle>
          <CardDescription>
            Decentralized social protocol
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 mb-6">
            <Button
              variant={mode === "login" ? "default" : "outline"}
              className="flex-1"
              onClick={() => setMode("login")}
            >
              Login
            </Button>
            <Button
              variant={mode === "register" ? "default" : "outline"}
              className="flex-1"
              onClick={() => setMode("register")}
            >
              Register
            </Button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" ? (
              <>
                <div>
                  <label className="text-sm font-medium">Handle</label>
                  <Input
                    placeholder="@yourhandle"
                    value={handle}
                    onChange={(e) => setHandle(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
                    className="mt-1"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Lowercase letters, numbers, and underscores only
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium">Display Name</label>
                  <Input
                    placeholder="Your Name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Bio (optional)</label>
                  <Input
                    placeholder="Tell us about yourself"
                    value={bio}
                    onChange={(e) => setBio(e.target.value)}
                    className="mt-1"
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  A cryptographic keypair will be generated for you. 
                  This is your identity — keep it safe!
                </p>
              </>
            ) : (
              <div className="text-center py-4">
                {hasExistingKeys ? (
                  <p className="text-sm text-muted-foreground">
                    Click below to sign in with your existing keys.
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No keys found. Please register first to create your identity.
                  </p>
                )}
              </div>
            )}

            {error && (
              <div className="p-3 text-sm text-red-600 bg-red-50 rounded-md">
                {error}
              </div>
            )}

            <Button 
              type="submit" 
              className="w-full" 
              disabled={loading || (mode === "login" && !hasExistingKeys)}
            >
              {loading ? "Please wait..." : mode === "login" ? "Sign In" : "Create Account"}
            </Button>
          </form>

          <div className="mt-6 pt-6 border-t">
            <p className="text-xs text-center text-muted-foreground">
              MESH is a decentralized protocol. Your data is stored locally 
              and synced across nodes. No central server owns your identity.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
