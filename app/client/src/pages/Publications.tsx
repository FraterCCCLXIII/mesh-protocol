import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Users, FileText } from "lucide-react";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Avatar, AvatarFallback } from "../components/ui/avatar";
import { apiCall, getStoredUser } from "../lib/mesh";

interface Publication {
  id: string;
  name: string;
  description: string;
  handle: string;
  owner_id: string;
  owner_handle: string;
  owner_profile: { name?: string };
  price_monthly: number;
  subscriber_count?: number;
}

export function PublicationsPage() {
  const [publications, setPublications] = useState<Publication[]>([]);
  const [loading, setLoading] = useState(true);
  const user = getStoredUser();

  useEffect(() => {
    async function load() {
      try {
        const data = await apiCall<{ items: Publication[] }>("/api/publications");
        setPublications(data.items || []);
      } catch (err) {
        console.error("Failed to load publications:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

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
        <main className="flex-1 border-x border-border min-h-screen">
          <div className="sticky top-0 z-10 bg-background/80 backdrop-blur border-b">
            <div className="flex items-center justify-between p-4">
              <h1 className="text-xl font-bold">Publications</h1>
              {user && (
                <Link to="/publications/new">
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
          ) : publications.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No publications yet</p>
              <p className="text-sm mt-2">Be the first to create one!</p>
            </div>
          ) : (
            <div className="p-4 grid gap-4 md:grid-cols-2">
              {publications.map((pub) => (
                <Link key={pub.id} to={`/publications/${pub.id}`}>
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
        </main>

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
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}

export default PublicationsPage;
