import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Lock, Calendar, Clock } from "lucide-react";
import { Button } from "../components/ui/button";
import { Avatar, AvatarFallback } from "../components/ui/avatar";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { apiCall, getStoredUser } from "../lib/mesh";
import { AppPageShell } from "../components/AppPageShell";

interface Article {
  id: string;
  publication_id: string;
  author_handle: string;
  author_profile?: { name?: string };
  title: string;
  subtitle: string;
  content: string | null;
  access: string;
  published_at: string;
  can_view: boolean;
  paywall_message: string | null;
}

interface Publication {
  id: string;
  name: string;
  price_monthly: number;
}

export function ArticlePage() {
  const { id } = useParams();
  const user = getStoredUser();
  const [article, setArticle] = useState<Article | null>(null);
  const [publication, setPublication] = useState<Publication | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      if (!id) return;
      try {
        const art = await apiCall<Article>(`/api/articles/${id}`);
        setArticle(art);
        const pub = await apiCall<Publication>(`/api/publications/${art.publication_id}`);
        setPublication(pub);
      } catch (err) {
        console.error("Failed to load article:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  const getInitials = (name?: string) =>
    name
      ?.split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2) || "?";

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleDateString("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric",
    });

  if (loading) {
    return (
      <AppPageShell>
        <div className="flex min-h-[40vh] items-center justify-center">
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </AppPageShell>
    );
  }

  if (!article) {
    return (
      <AppPageShell>
        <div className="flex min-h-[40vh] items-center justify-center">
          <p className="text-muted-foreground">Article not found</p>
        </div>
      </AppPageShell>
    );
  }

  const wordCount = article.content?.split(/\s+/).filter(Boolean).length || 0;
  const readTime = Math.ceil(wordCount / 200);

  return (
    <AppPageShell>
    <div className="min-h-screen w-full bg-background">
      <header className="border-b">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link to={`/publications/${article.publication_id}`}>
            <Button variant="ghost" size="icon">
              <ArrowLeft className="w-5 h-5" />
            </Button>
          </Link>
          <Link
            to={`/publications/${article.publication_id}`}
            className="font-semibold hover:underline"
          >
            {publication?.name}
          </Link>
        </div>
      </header>

      <article className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-4xl font-bold">{article.title}</h1>
        {article.subtitle && (
          <p className="text-xl text-muted-foreground mt-2">{article.subtitle}</p>
        )}

        <div className="flex items-center gap-4 mt-6 py-4 border-y">
          <Avatar>
            <AvatarFallback>
              {getInitials(article.author_profile?.name)}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1">
            <p className="font-medium">
              {article.author_profile?.name || article.author_handle}
            </p>
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <Calendar className="w-4 h-4" />
                {formatDate(article.published_at)}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                {readTime} min read
              </span>
              {article.access !== "public" && (
                <span className="flex items-center gap-1">
                  <Lock className="w-4 h-4" />
                  {article.access === "paid" ? "Paid" : "Subscribers"}
                </span>
              )}
            </div>
          </div>
        </div>

        {article.can_view && article.content ? (
          <div className="prose prose-lg mt-8 max-w-none">
            {article.content.split("\n\n").map((para, i) => (
              <p key={i} className="my-4 leading-relaxed">
                {para}
              </p>
            ))}
          </div>
        ) : (
          <div className="mt-8">
            <Card className="bg-muted/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Lock className="w-5 h-5" />
                  {article.paywall_message || "Subscribe to continue reading"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground mb-4">
                  This article is for {article.access === "paid" ? "paid " : ""}
                  subscribers of {publication?.name}.
                </p>
                <Link to={`/publications/${article.publication_id}`}>
                  <Button>Subscribe</Button>
                </Link>
              </CardContent>
            </Card>
          </div>
        )}
      </article>
    </div>
    </AppPageShell>
  );
}

export default ArticlePage;
