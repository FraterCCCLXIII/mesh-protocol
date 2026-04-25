import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Sidebar } from "../components/Sidebar";
import { apiCall } from "../lib/mesh";

export function NewPublicationPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [handle, setHandle] = useState("");
  const [priceMonthly, setPriceMonthly] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const result = await apiCall<{ id: string }>("/api/publications", {
        method: "POST",
        body: JSON.stringify({
          name,
          description: description || null,
          handle: handle || null,
          price_monthly: priceMonthly ? Math.round(parseFloat(priceMonthly) * 100) : 0,
          price_yearly: 0,
        }),
      });

      navigate(`/publications/${result.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create publication");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto flex">
        <Sidebar />

        <main className="flex-1 border-x border-border min-h-screen">
          <div className="sticky top-0 z-10 bg-background/80 backdrop-blur border-b">
            <div className="flex items-center gap-4 p-4">
              <Link to="/publications">
                <Button variant="ghost" size="icon">
                  <ArrowLeft className="w-5 h-5" />
                </Button>
              </Link>
              <h1 className="text-xl font-bold">Create Publication</h1>
            </div>
          </div>

          <div className="p-4 max-w-xl mx-auto">
            <Card>
              <CardHeader>
                <CardTitle>New Publication</CardTitle>
                <CardDescription>
                  Start your own newsletter and build an audience
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  {error && (
                    <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                      {error}
                    </div>
                  )}

                  <div className="space-y-2">
                    <label className="text-sm font-medium">Name *</label>
                    <Input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="My Awesome Newsletter"
                      required
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">Handle</label>
                    <Input
                      value={handle}
                      onChange={(e) => setHandle(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                      placeholder="my-newsletter"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">Description</label>
                    <Input
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="What will you write about?"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">Monthly Price ($)</label>
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={priceMonthly}
                      onChange={(e) => setPriceMonthly(e.target.value)}
                      placeholder="0 for free"
                    />
                  </div>

                  <Button type="submit" className="w-full" disabled={loading || !name}>
                    {loading ? "Creating..." : "Create Publication"}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>
        </main>

        <aside className="w-80 p-4 hidden lg:block" />
      </div>
    </div>
  );
}

export default NewPublicationPage;
