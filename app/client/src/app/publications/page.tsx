"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Users, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Sidebar } from "@/components/sidebar";
import { apiCall, getStoredToken, getStoredUser } from "@/lib/mesh";

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
  subscriber_count?: number;
  created_at: string;
}

export default function PublicationsPage() {
  const [publications, setPublications] = useState<Publication[]>([]);
  const [myPublications, setMyPublications] = useState<Publication[]>([]);
  const [loading, setLoading] = useState(true);
  const user = getStoredUser();

  useEffect(() => {
    async function load() {
      try {
        // Get all publications
        const all = await apiCall<{ items: Publication[] }>("/api/publications");
        setPublications(all.items);

        // Get my publications
        if (user) {
          const mine = await apiCall<{ items: Publication[] }>(
            `/api/publications?owner_id=${user.id}`
          );
          setMyPublications(mine.items);
        }
      } catch (err) {
        console.error("Failed to load publications:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [user]);

  const getInitials = (name?: string) =>
    name
      ?.split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2) || "?";

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto flex">
        <Sidebar />
        <main className="flex-1 border-x border-border min-h-screen">
          {/* Header */}
          <div className="sticky top-0 z-10 bg-background/80 backdrop-blur border-b">
            <div className="flex items-center justify-between p-4">
              <h1 className="text-xl font-bold">Publications</h1>
              {user && (
                <Link href="/publications/new">
                  <Button>
                    <Plus className="w-4 h-4 mr-2" />
                    New Publication
                  </Button>
                </Link>
              )}
            </div>
          </div>

          {loading ? (
            <div className="p-8 text-center text-muted-foreground">Loading...</div>
          ) : (
            <div className="p-4 space-y-8">
              {/* My Publications */}
              {myPublications.length > 0 && (
                <section>
                  <h2 className="text-lg font-semibold mb-4">My Publications</h2>
                  <div className="grid gap-4 md:grid-cols-2">
                    {myPublications.map((pub) => (
                      <Link key={pub.id} href={`/publications/${pub.id}`}>
                        <Card className="hover:bg-muted/50 transition cursor-pointer h-full">
                          <CardHeader>
                            <CardTitle>{pub.name}</CardTitle>
                            <CardDescription>@{pub.handle || pub.id.slice(4, 12)}</CardDescription>
                          </CardHeader>
                          <CardContent>
                            <p className="text-sm text-muted-foreground line-clamp-2">
                              {pub.description || "No description"}
                            </p>
                            <div className="flex items-center gap-4 mt-4 text-sm text-muted-foreground">
                              <span className="flex items-center gap-1">
                                <Users className="w-4 h-4" />
                                {pub.subscriber_count || 0} subscribers
                              </span>
                              {pub.price_monthly > 0 && (
                                <span>${(pub.price_monthly / 100).toFixed(2)}/mo</span>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      </Link>
                    ))}
                  </div>
                </section>
              )}

              {/* All Publications */}
              <section>
                <h2 className="text-lg font-semibold mb-4">Discover Publications</h2>
                {publications.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground">
                    <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>No publications yet</p>
                    <p className="text-sm mt-2">Be the first to create one!</p>
                  </div>
                ) : (
                  <div className="grid gap-4 md:grid-cols-2">
                    {publications.map((pub) => (
                      <Link key={pub.id} href={`/publications/${pub.id}`}>
                        <Card className="hover:bg-muted/50 transition cursor-pointer h-full">
                          <CardHeader className="flex flex-row items-start gap-4">
                            <Avatar>
                              <AvatarFallback>
                                {getInitials(pub.owner_profile?.name || pub.name)}
                              </AvatarFallback>
                            </Avatar>
                            <div className="flex-1">
                              <CardTitle className="text-base">{pub.name}</CardTitle>
                              <CardDescription>
                                by {pub.owner_profile?.name || pub.owner_handle || "Anonymous"}
                              </CardDescription>
                            </div>
                          </CardHeader>
                          <CardContent>
                            <p className="text-sm text-muted-foreground line-clamp-2">
                              {pub.description || "No description"}
                            </p>
                            <div className="flex items-center justify-between mt-4 text-sm">
                              <span className="text-muted-foreground flex items-center gap-1">
                                <Users className="w-4 h-4" />
                                {pub.subscriber_count || 0}
                              </span>
                              {pub.price_monthly > 0 ? (
                                <span className="font-medium">
                                  ${(pub.price_monthly / 100).toFixed(2)}/mo
                                </span>
                              ) : (
                                <span className="text-green-600 font-medium">Free</span>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      </Link>
                    ))}
                  </div>
                )}
              </section>
            </div>
          )}
        </main>

        {/* Right Sidebar */}
        <aside className="w-80 p-4 hidden lg:block">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">About Publications</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <p>
                Publications are like newsletters. Create one to share long-form
                content with your subscribers.
              </p>
              <p className="mt-2">
                Set a price to monetize your writing with paid subscriptions.
              </p>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
