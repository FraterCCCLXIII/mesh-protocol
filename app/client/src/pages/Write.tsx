import { useState, useEffect } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { ArrowLeft, Save, Send } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { apiCall, getStoredUser } from "../lib/mesh";

export function WritePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const publicationId = searchParams.get("publication");
  const user = getStoredUser();

  const [pubName, setPubName] = useState("");
  const [title, setTitle] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [content, setContent] = useState("");
  const [access, setAccess] = useState("public");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (publicationId) {
      apiCall<{ name: string }>(`/api/publications/${publicationId}`).then((p) =>
        setPubName(p.name)
      );
    }
  }, [publicationId]);

  const handleSave = async (status: "draft" | "published") => {
    if (!publicationId || !title || !content) {
      setError("Title and content are required");
      return;
    }

    setSaving(true);
    setError("");

    try {
      const result = await apiCall<{ id: string }>("/api/articles", {
        method: "POST",
        body: JSON.stringify({
          publication_id: publicationId,
          title,
          subtitle: subtitle || null,
          content,
          access,
          status,
        }),
      });

      if (status === "published") {
        navigate(`/article/${result.id}`);
      } else {
        navigate(`/publications/${publicationId}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">Please log in to write articles</p>
      </div>
    );
  }

  if (!publicationId) {
    return (
      <div className="min-h-screen flex items-center justify-center flex-col gap-4">
        <p className="text-muted-foreground">Select a publication to write for</p>
        <Link to="/publications">
          <Button>Browse Publications</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto">
        <header className="sticky top-0 z-10 bg-background border-b">
          <div className="flex items-center justify-between p-4">
            <div className="flex items-center gap-4">
              <Link to={`/publications/${publicationId}`}>
                <Button variant="ghost" size="icon">
                  <ArrowLeft className="w-5 h-5" />
                </Button>
              </Link>
              <span className="text-muted-foreground">
                Writing in <strong>{pubName || "..."}</strong>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={access}
                onChange={(e) => setAccess(e.target.value)}
                className="border rounded px-3 py-1.5 text-sm bg-background"
              >
                <option value="public">Public</option>
                <option value="subscribers">Subscribers Only</option>
                <option value="paid">Paid Only</option>
              </select>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleSave("draft")}
                disabled={saving}
              >
                <Save className="w-4 h-4 mr-2" />
                Draft
              </Button>
              <Button size="sm" onClick={() => handleSave("published")} disabled={saving}>
                <Send className="w-4 h-4 mr-2" />
                Publish
              </Button>
            </div>
          </div>
        </header>

        <main className="p-8">
          {error && (
            <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {error}
            </div>
          )}

          <div className="space-y-6">
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Article title..."
              className="text-3xl font-bold border-0 border-b rounded-none px-0 focus-visible:ring-0"
            />

            <Input
              value={subtitle}
              onChange={(e) => setSubtitle(e.target.value)}
              placeholder="Add a subtitle (optional)..."
              className="text-xl text-muted-foreground border-0 border-b rounded-none px-0 focus-visible:ring-0"
            />

            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Start writing your article..."
              className="w-full min-h-[500px] text-lg leading-relaxed border-0 resize-none focus:outline-none"
            />
          </div>
        </main>

        <footer className="fixed bottom-0 left-0 right-0 border-t bg-background/80 backdrop-blur">
          <div className="max-w-4xl mx-auto px-8 py-3 flex justify-between text-sm text-muted-foreground">
            <span>{content.split(/\s+/).filter(Boolean).length} words</span>
            <span>{Math.ceil(content.split(/\s+/).filter(Boolean).length / 200)} min read</span>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default WritePage;
