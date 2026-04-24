import { useState } from "react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { registerUser, loginUser } from "../lib/mesh";

interface AuthPageProps {
  onAuth: () => void;
}

export function AuthPage({ onAuth }: AuthPageProps) {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [name, setName] = useState("");
  const [handle, setHandle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      if (mode === "register") {
        await registerUser(handle, name);
      } else {
        await loginUser(handle);
      }
      onAuth();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="w-12 h-12 rounded-full bg-foreground flex items-center justify-center mx-auto mb-4">
            <span className="text-background font-bold text-xl">M</span>
          </div>
          <CardTitle className="text-2xl">Welcome to MESH</CardTitle>
          <CardDescription>
            A decentralized social network with self-sovereign identity
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                {error}
              </div>
            )}

            {mode === "register" && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Display Name</label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your Name"
                  required
                />
              </div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium">Handle</label>
              <Input
                value={handle}
                onChange={(e) => setHandle(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
                placeholder="username"
                required
              />
            </div>

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Please wait..." : mode === "register" ? "Create Account" : "Sign In"}
            </Button>

            <div className="text-center text-sm">
              {mode === "register" ? (
                <p>
                  Already have an account?{" "}
                  <button
                    type="button"
                    onClick={() => setMode("login")}
                    className="text-primary hover:underline"
                  >
                    Sign in
                  </button>
                </p>
              ) : (
                <p>
                  Need an account?{" "}
                  <button
                    type="button"
                    onClick={() => setMode("register")}
                    className="text-primary hover:underline"
                  >
                    Register
                  </button>
                </p>
              )}
            </div>
          </form>

          <div className="mt-6 pt-6 border-t text-center text-xs text-muted-foreground">
            <p>Your keys are generated locally and never leave your device.</p>
            <p className="mt-1">This is a decentralized protocol demo.</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
