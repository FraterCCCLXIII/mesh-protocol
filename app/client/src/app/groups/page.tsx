"use client";

import { useEffect, useState } from "react";
import { Plus, Users, Lock, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Sidebar } from "@/components/sidebar";
import { getGroups, createGroup, joinGroup, type Group } from "@/lib/mesh";

export default function GroupsPage() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newAccess, setNewAccess] = useState<"public" | "private">("public");
  const [creating, setCreating] = useState(false);

  const loadGroups = async () => {
    try {
      const result = await getGroups();
      setGroups(result.items);
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
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await createGroup(newName, newDescription, newAccess);
      setNewName("");
      setNewDescription("");
      setShowCreate(false);
      loadGroups();
    } catch (err) {
      console.error("Failed to create group:", err);
    } finally {
      setCreating(false);
    }
  };

  const handleJoin = async (groupId: string) => {
    try {
      await joinGroup(groupId);
      loadGroups();
    } catch (err) {
      console.error("Failed to join group:", err);
    }
  };

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
            <div className="p-4 border-b">
              <Card>
                <CardHeader>
                  <CardTitle>Create a Group</CardTitle>
                  <CardDescription>
                    Groups let you create communities around topics
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <label className="text-sm font-medium">Group Name</label>
                    <Input
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      placeholder="My Awesome Group"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Description</label>
                    <Input
                      value={newDescription}
                      onChange={(e) => setNewDescription(e.target.value)}
                      placeholder="What's this group about?"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Access</label>
                    <div className="flex gap-2 mt-2">
                      <Button
                        variant={newAccess === "public" ? "default" : "outline"}
                        onClick={() => setNewAccess("public")}
                        className="flex-1"
                      >
                        <Globe className="w-4 h-4 mr-2" />
                        Public
                      </Button>
                      <Button
                        variant={newAccess === "private" ? "default" : "outline"}
                        onClick={() => setNewAccess("private")}
                        className="flex-1"
                      >
                        <Lock className="w-4 h-4 mr-2" />
                        Private
                      </Button>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button 
                      variant="outline" 
                      onClick={() => setShowCreate(false)}
                      className="flex-1"
                    >
                      Cancel
                    </Button>
                    <Button 
                      onClick={handleCreate}
                      disabled={creating || !newName.trim()}
                      className="flex-1"
                    >
                      {creating ? "Creating..." : "Create Group"}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Groups List */}
          <div className="p-4">
            {loading ? (
              <div className="text-center text-muted-foreground py-8">
                Loading groups...
              </div>
            ) : groups.length === 0 ? (
              <div className="text-center text-muted-foreground py-8">
                <Users className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No groups yet</p>
                <p className="text-sm">Create one to get started!</p>
              </div>
            ) : (
              <div className="space-y-3">
                {groups.map((group) => (
                  <Card key={group.id} className="hover:bg-muted/50 transition-colors">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold">{group.name}</h3>
                            {group.access === "private" ? (
                              <Lock className="w-4 h-4 text-muted-foreground" />
                            ) : (
                              <Globe className="w-4 h-4 text-muted-foreground" />
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground mt-1">
                            {group.description || "No description"}
                          </p>
                          <p className="text-xs text-muted-foreground mt-2">
                            {group.member_count} members
                          </p>
                        </div>
                        <Button 
                          variant="outline"
                          onClick={() => handleJoin(group.id)}
                        >
                          Join
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </main>
        <aside className="w-80 p-4 hidden lg:block" />
      </div>
    </div>
  );
}
