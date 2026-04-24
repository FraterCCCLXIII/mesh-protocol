"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Lock, Calendar, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Sidebar } from "@/components/sidebar";
import { apiCall, getStoredUser } from "@/lib/mesh";

interface Article {
  id: string;
  publication_id: string;
  author_id: string;
  author_handle: string;
  author_profile?: { name?: string };
  title: string;
  subtitle: string;
  content: string | null;
  excerpt: string;
  cover_image: string;
  access: string;
  status: string;
  published_at: string;
  can_view: boolean;
  paywall_message: string | null;
}

interface Publication {
  id: string;
  name: string;
  price_monthly: number;
}

export default function ArticlePage() {
  const params = useParams();
  const articleId = params.id as string;
  const user = getStoredUser();

  const [article, setArticle] = useState<Article | null>(null);
  const [publication, setPublication] = useState<Publication | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const articleData = await apiCall<Article>(`/api/articles/${articleId}`);
        setArticle(articleData);

        const pubData = await apiCall<Publication>(
          `/api/publications/${articleData.publication_id}`
        );
        setPublication(pubData);
      } catch (err) {
        console.error("Failed to load article:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [articleId]);

  const handleSubscribe = async () => {
    if (!article || !publication) return;

    if (publication.price_monthly > 0) {
      try {
        const result = await apiCall<{ checkout_url: string }>(
          "/api/stripe/create-checkout-session",
          {
            method: "POST",
            body: JSON.stringify({
              publication_id: article.publication_id,
              billing_cycle: "monthly",
            }),
          }
        );
        if (result.checkout_url) {
          window.location.href = result.checkout_url;
        }
      } catch (err) {
        // Fall back to free subscription
        await apiCall("/api/subscriptions", {
          method: "POST",
          body: JSON.stringify({
            publication_id: article.publication_id,
            tier: "free",
          }),
        });
        window.location.reload();
      }
    } else {
      await apiCall("/api/subscriptions", {
        method: "POST",
        body: JSON.stringify({
          publication_id: article.publication_id,
          tier: "free",
        }),
      });
      window.location.reload();
    }
  };

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

  const renderContent = (content: string) => {
    // Simple markdown-ish rendering
    return content
      .split("\n\n")
      .map((para, i) => {
        // Headings
        if (para.startsWith("# ")) {
          return (
            <h2 key={i} className="text-2xl font-bold mt-8 mb-4">
              {para.slice(2)}
            </h2>
          );
        }
        if (para.startsWith("## ")) {
          return (
            <h3 key={i} className="text-xl font-semibold mt-6 mb-3">
              {para.slice(3)}
            </h3>
          );
        }
        // Blockquotes
        if (para.startsWith("> ")) {
          return (
            <blockquote
              key={i}
              className="border-l-4 border-muted-foreground/30 pl-4 italic my-4"
            >
              {para.slice(2)}
            </blockquote>
          );
        }
        // Regular paragraphs
        return (
          <p key={i} className="my-4 leading-relaxed">
            {para}
          </p>
        );
      });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!article) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">Article not found</p>
      </div>
    );
  }

  const wordCount = article.content?.split(/\s+/).filter(Boolean).length || 0;
  const readTime = Math.ceil(wordCount / 200);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link href={`/publications/${article.publication_id}`}>
            <Button variant="ghost" size="icon">
              <ArrowLeft className="w-5 h-5" />
            </Button>
          </Link>
          <Link
            href={`/publications/${article.publication_id}`}
            className="font-semibold hover:underline"
          >
            {publication?.name}
          </Link>
        </div>
      </header>

      {/* Article */}
      <article className="max-w-3xl mx-auto px-4 py-8">
        {/* Cover Image */}
        {article.cover_image && (
          <img
            src={article.cover_image}
            alt=""
            className="w-full h-64 object-cover rounded-lg mb-8"
          />
        )}

        {/* Title */}
        <h1 className="text-4xl font-bold">{article.title}</h1>
        {article.subtitle && (
          <p className="text-xl text-muted-foreground mt-2">{article.subtitle}</p>
        )}

        {/* Author & Meta */}
        <div className="flex items-center gap-4 mt-6 py-4 border-y">
          <Avatar>
            <AvatarFallback>
              {getInitials(article.author_profile?.name)}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1">
            <p className="font-medium">
              {article.author_profile?.name || article.author_handle || "Anonymous"}
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

        {/* Content or Paywall */}
        {article.can_view && article.content ? (
          <div className="prose prose-lg mt-8 max-w-none">
            {renderContent(article.content)}
          </div>
        ) : (
          <div className="mt-8">
            {/* Show excerpt */}
            {article.excerpt && (
              <div className="prose prose-lg max-w-none mb-8">
                <p className="leading-relaxed">{article.excerpt}</p>
              </div>
            )}

            {/* Paywall */}
            <Card className="bg-muted/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Lock className="w-5 h-5" />
                  {article.paywall_message || "Subscribe to continue reading"}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-muted-foreground">
                  This article is for {article.access === "paid" ? "paid" : ""} subscribers
                  of {publication?.name}.
                </p>
                {user ? (
                  <Button onClick={handleSubscribe}>
                    {publication && publication.price_monthly > 0
                      ? `Subscribe for $${(publication.price_monthly / 100).toFixed(2)}/mo`
                      : "Subscribe Free"}
                  </Button>
                ) : (
                  <Link href="/">
                    <Button>Sign in to subscribe</Button>
                  </Link>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </article>
    </div>
  );
}
