"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Users, PenLine, Lock, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Sidebar } from "@/components/sidebar";
import { apiCall, getStoredUser } from "@/lib/mesh";

interface Publication {
  id: string;
  name: string;
  description: string;
  handle: string;
  owner_id: string;
  owner_handle: string;
  owner_profile: { name?: string };
  price_monthly: number;
  price_yearly: number;
  subscriber_count: number;
  created_at: string;
}

interface Article {
  id: string;
  title: string;
  subtitle: string;
  excerpt: string;
  cover_image: string;
  access: string;
  status: string;
  published_at: string;
  can_view: boolean;
  author_profile?: { name?: string };
}

export default function PublicationPage() {
  const params = useParams();
  const pubId = params.id as string;
  const user = getStoredUser();

  const [publication, setPublication] = useState<Publication | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [subscriptionTier, setSubscriptionTier] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [pubData, articlesData] = await Promise.all([
        apiCall<Publication>(`/api/publications/${pubId}`),
        apiCall<{ items: Article[] }>(`/api/articles?publication_id=${pubId}`),
      ]);
      setPublication(pubData);
      setArticles(articlesData.items);

      // Check subscription status
      if (user) {
        try {
          const subs = await apiCall<{ items: { publication_id: string; tier: string }[] }>(
            "/api/subscriptions"
          );
          const sub = subs.items.find((s) => s.publication_id === pubId);
          if (sub) {
            setIsSubscribed(true);
            setSubscriptionTier(sub.tier);
          }
        } catch {
          // Not subscribed
        }
      }
    } catch (err) {
      console.error("Failed to load publication:", err);
    } finally {
      setLoading(false);
    }
  }, [pubId, user]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSubscribe = async (tier: string) => {
    if (!user) {
      window.location.href = "/";
      return;
    }

    try {
      if (tier === "paid" && publication && publication.price_monthly > 0) {
        // Redirect to Stripe checkout
        const result = await apiCall<{ checkout_url: string }>(
          "/api/stripe/create-checkout-session",
          {
            method: "POST",
            body: JSON.stringify({
              publication_id: pubId,
              billing_cycle: "monthly",
            }),
          }
        );
        if (result.checkout_url) {
          window.location.href = result.checkout_url;
          return;
        }
      }

      // Free subscription
      await apiCall("/api/subscriptions", {
        method: "POST",
        body: JSON.stringify({
          publication_id: pubId,
          tier,
        }),
      });
      setIsSubscribed(true);
      setSubscriptionTier(tier);
      loadData();
    } catch (err) {
      console.error("Failed to subscribe:", err);
    }
  };

  const isOwner = user && publication && user.id === publication.owner_id;

  const getInitials = (name?: string) =>
    name
      ?.split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2) || "?";

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!publication) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Publication not found</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto flex">
        <Sidebar />
        <main className="flex-1 border-x border-border min-h-screen">
          {/* Header */}
          <div className="sticky top-0 z-10 bg-background/80 backdrop-blur border-b">
            <div className="flex items-center gap-4 p-4">
              <Link href="/publications">
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
                  by {publication.owner_profile?.name || publication.owner_handle || "Anonymous"}
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

            {/* Action Buttons */}
            <div className="mt-6 flex gap-3">
              {isOwner ? (
                <Link href={`/write?publication=${pubId}`}>
                  <Button>
                    <PenLine className="w-4 h-4 mr-2" />
                    Write Article
                  </Button>
                </Link>
              ) : isSubscribed ? (
                <Button variant="outline" disabled>
                  <Check className="w-4 h-4 mr-2" />
                  Subscribed ({subscriptionTier})
                </Button>
              ) : (
                <div className="flex gap-2">
                  <Button onClick={() => handleSubscribe("free")}>
                    Subscribe Free
                  </Button>
                  {publication.price_monthly > 0 && (
                    <Button variant="outline" onClick={() => handleSubscribe("paid")}>
                      Paid (${(publication.price_monthly / 100).toFixed(2)}/mo)
                    </Button>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Articles */}
          <div className="divide-y">
            {articles.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                <PenLine className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No articles yet</p>
                {isOwner && (
                  <Link href={`/write?publication=${pubId}`}>
                    <Button variant="link">Write your first article</Button>
                  </Link>
                )}
              </div>
            ) : (
              articles.map((article) => (
                <Link
                  key={article.id}
                  href={`/article/${article.id}`}
                  className="block p-6 hover:bg-muted/50 transition"
                >
                  <div className="flex gap-4">
                    {article.cover_image && (
                      <img
                        src={article.cover_image}
                        alt=""
                        className="w-32 h-24 object-cover rounded"
                      />
                    )}
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-lg">{article.title}</h3>
                        {article.access !== "public" && (
                          <Lock className="w-4 h-4 text-muted-foreground" />
                        )}
                      </div>
                      {article.subtitle && (
                        <p className="text-muted-foreground">{article.subtitle}</p>
                      )}
                      {article.excerpt && (
                        <p className="text-sm text-muted-foreground mt-2 line-clamp-2">
                          {article.excerpt}
                        </p>
                      )}
                      <p className="text-xs text-muted-foreground mt-2">
                        {formatDate(article.published_at)}
                      </p>
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>
        </main>

        {/* Right Sidebar */}
        <aside className="w-80 p-4 hidden lg:block">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">About</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <p>{publication.description || "No description provided"}</p>
              <div className="mt-4 pt-4 border-t">
                <p className="font-medium text-foreground mb-2">Subscription tiers</p>
                <ul className="space-y-2">
                  <li className="flex justify-between">
                    <span>Free</span>
                    <span className="text-green-600">$0</span>
                  </li>
                  {publication.price_monthly > 0 && (
                    <>
                      <li className="flex justify-between">
                        <span>Monthly</span>
                        <span>${(publication.price_monthly / 100).toFixed(2)}</span>
                      </li>
                      {publication.price_yearly > 0 && (
                        <li className="flex justify-between">
                          <span>Yearly</span>
                          <span>${(publication.price_yearly / 100).toFixed(2)}</span>
                        </li>
                      )}
                    </>
                  )}
                </ul>
              </div>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
