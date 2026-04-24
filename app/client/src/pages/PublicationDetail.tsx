import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Users, PenLine, Check } from "lucide-react";
import { Button } from "../components/ui/button";
import { Avatar, AvatarFallback } from "../components/ui/avatar";
import { Sidebar } from "../components/Sidebar";
import { apiCall, getStoredUser } from "../lib/mesh";

interface Publication {
  id: string;
  name: string;
  description: string;
  owner_id: string;
  owner_handle: string;
  owner_profile: { name?: string };
  price_monthly: number;
  subscriber_count: number;
}

interface Article {
  id: string;
  title: string;
  subtitle: string;
  excerpt: string;
  published_at: string;
}

export function PublicationDetailPage() {
  const { id } = useParams();
  const user = getStoredUser();
  const [publication, setPublication] = useState<Publication | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      if (!id) return;
      try {
        const [pub, arts] = await Promise.all([
          apiCall<Publication>(`/api/publications/${id}`),
          apiCall<{ items: Article[] }>(`/api/articles?publication_id=${id}`),
        ]);
        setPublication(pub);
        setArticles(arts.items || []);
      } catch (err) {
        console.error("Failed to load publication:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  const handleSubscribe = async () => {
    if (!user || !id) return;
    try {
      await apiCall("/api/subscriptions", {
        method: "POST",
        body: JSON.stringify({ publication_id: id, tier: "free" }),
      });
      setIsSubscribed(true);
    } catch (err) {
      console.error("Failed to subscribe:", err);
    }
  };

  const getInitials = (name?: string) =>
    name
      ?.split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2) || "?";

  const isOwner = user && publication && user.id === publication.owner_id;

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!publication) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">Publication not found</p>
      </div>
    );
  }

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
              <h1 className="text-xl font-bold">{publication.name}</h1>
            </div>
          </div>

          {/* Publication Header */}
          <div className="p-6 border-b">
            <div className="flex items-start gap-4">
              <Avatar className="w-16 h-16">
                <AvatarFallback className="text-xl">
                  {getInitials(publication.name)}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1">
                <h2 className="text-2xl font-bold">{publication.name}</h2>
                <p className="text-muted-foreground">
                  by {publication.owner_profile?.name || publication.owner_handle}
                </p>
                {publication.description && (
                  <p className="mt-2">{publication.description}</p>
                )}
                <div className="flex items-center gap-4 mt-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Users className="w-4 h-4" />
                    {publication.subscriber_count} subscribers
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-6 flex gap-3">
              {isOwner ? (
                <Link to={`/write?publication=${id}`}>
                  <Button>
                    <PenLine className="w-4 h-4 mr-2" />
                    Write Article
                  </Button>
                </Link>
              ) : isSubscribed ? (
                <Button variant="outline" disabled>
                  <Check className="w-4 h-4 mr-2" />
                  Subscribed
                </Button>
              ) : (
                <Button onClick={handleSubscribe}>Subscribe Free</Button>
              )}
            </div>
          </div>

          {/* Articles */}
          <div className="divide-y">
            {articles.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                <PenLine className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No articles yet</p>
              </div>
            ) : (
              articles.map((article) => (
                <Link
                  key={article.id}
                  to={`/article/${article.id}`}
                  className="block p-6 hover:bg-muted/50 transition"
                >
                  <h3 className="font-semibold text-lg">{article.title}</h3>
                  {article.subtitle && (
                    <p className="text-muted-foreground">{article.subtitle}</p>
                  )}
                  {article.excerpt && (
                    <p className="text-sm text-muted-foreground mt-2 line-clamp-2">
                      {article.excerpt}
                    </p>
                  )}
                </Link>
              ))
            )}
          </div>
        </main>

        <aside className="w-80 p-4 hidden lg:block" />
      </div>
    </div>
  );
}
