import { useEffect, useState } from "react";
import { Plus, Users, Lock, Globe } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Avatar, AvatarFallback } from "../components/ui/avatar";
import { Sidebar } from "../components/Sidebar";
import { apiCall, getStoredToken } from "../lib/mesh";

interface Group {
  id: string;
  name: string;
  description?: string;
  profile?: { description?: string };
  privacy: string;
  member_count: number;
  created_at: string;
}

export function GroupsPage() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  const loadGroups = async () => {
    setLoading(true);
    try {
      const data = await apiCall<{ items: Group[] }>("/api/groups");
      setGroups(data.items || []);
    } catch (err) {
      console.error("Failed to load groups:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGroups();
  }, []);

  const handleCreate = async () => {
    if (!newName.trim() || creating) return;
    
    setCreating(true);
    try {
      await apiCall("/api/groups", {
        method: "POST",
        body: JSON.stringify({
          name: newName,
          description: newDesc || null,
          privacy: "public",
        }),
      });
      setNewName("");
      setNewDesc("");
      setShowCreate(false);
      loadGroups();
    } catch (err) {
      console.error("Failed to create group:", err);
    } finally {
      setCreating(false);
    }
  };

  const getInitials = (name: string) =>
    name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto flex">
        <Sidebar />

        <main className="flex-1 border-x border-border min-h-screen">
          {/* Header */}
          <div className="sticky top-0 z-10 bg-background/80 backdrop-blur border-b">
            <div className="flex items-center justify-between p-4">
              <h1 className="text-xl font-bold">Groups</h1>
              <Button onClick={() => setShowCreate(!showCreate)}>
                <Plus className="w-4 h-4 mr-2" />
                Create Group
              </Button>
            </div>
          </div>

          {/* Create Form */}
          {showCreate && (
            <div className="p-4 border-b bg-muted/30">
              <div className="space-y-3">
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Group name"
                />
                <Input
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Description (optional)"
                />
                <div className="flex gap-2">
                  <Button onClick={handleCreate} disabled={!newName.trim() || creating}>
                    {creating ? "Creating..." : "Create"}
                  </Button>
                  <Button variant="outline" onClick={() => setShowCreate(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Groups List */}
          {loading ? (
            <div className="p-8 text-center text-muted-foreground">Loading...</div>
          ) : groups.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <Users className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No groups yet</p>
              <p className="text-sm mt-2">Create the first group!</p>
            </div>
          ) : (
            <div className="divide-y">
              {groups.map((group) => (
                <div key={group.id} className="p-4 hover:bg-muted/30 transition">
                  <div className="flex items-start gap-3">
                    <Avatar className="w-12 h-12">
                      <AvatarFallback>{getInitials(group.name)}</AvatarFallback>
                    </Avatar>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold">{group.name}</h3>
                        {group.privacy === "private" ? (
                          <Lock className="w-4 h-4 text-muted-foreground" />
                        ) : (
                          <Globe className="w-4 h-4 text-muted-foreground" />
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {group.description || group.profile?.description || "No description"}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {group.member_count || 0} members
                      </p>
                    </div>
                    <Button variant="outline" size="sm">
                      Join
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </main>

        <aside className="w-80 p-4 hidden lg:block">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">About Groups</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <p>
                Groups let you create communities around shared interests.
                Groups can be public or private.
              </p>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
