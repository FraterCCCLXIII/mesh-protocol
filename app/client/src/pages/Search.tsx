/**
 * Search Results Page
 */
import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuth } from '@/contexts/AuthContext';
import { PostCard } from '@/components/PostCard';
import { Search as SearchIcon, Users, FileText, Hash, TrendingUp } from 'lucide-react';

interface SearchResult {
  type: 'user' | 'post' | 'group';
  id: string;
  data: any;
}

const API_URL = '/api';

export default function Search() {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get('q') || '';
  const { token } = useAuth();
  
  const [searchQuery, setSearchQuery] = useState(query);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'all' | 'users' | 'posts' | 'groups'>('all');
  const [trending, setTrending] = useState<string[]>([]);

  useEffect(() => {
    if (query) {
      performSearch(query);
    } else {
      loadTrending();
    }
  }, [query]);

  async function loadTrending() {
    try {
      const resp = await fetch(`${API_URL}/trending`);
      if (resp.ok) {
        const data = await resp.json();
        setTrending(data.topics || []);
      }
    } catch (err) {
      console.error('Failed to load trending:', err);
    }
  }

  async function performSearch(q: string) {
    if (!q.trim()) return;
    
    setIsLoading(true);
    try {
      const resp = await fetch(`${API_URL}/search?q=${encodeURIComponent(q)}${token ? `&token=${token}` : ''}`);
      if (resp.ok) {
        const data = await resp.json();
        setResults(data.results || []);
      }
    } catch (err) {
      console.error('Search failed:', err);
    } finally {
      setIsLoading(false);
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (searchQuery.trim()) {
      setSearchParams({ q: searchQuery });
    }
  }

  const filteredResults = activeTab === 'all' 
    ? results 
    : results.filter(r => r.type === activeTab.slice(0, -1)); // Remove 's' from end

  const userResults = results.filter(r => r.type === 'user');
  const postResults = results.filter(r => r.type === 'post');
  const groupResults = results.filter(r => r.type === 'group');

  return (
    <div className="max-w-2xl mx-auto">
      {/* Search Header */}
      <div className="sticky top-0 bg-background/95 backdrop-blur border-b z-10 p-4">
        <form onSubmit={handleSearch}>
          <div className="relative">
            <SearchIcon className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search MESH..."
              className="pl-9 pr-20"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
            <Button 
              type="submit" 
              size="sm" 
              className="absolute right-1 top-1"
              disabled={!searchQuery.trim()}
            >
              Search
            </Button>
          </div>
        </form>
      </div>

      {query ? (
        <>
          {/* Results Tabs */}
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)}>
            <TabsList className="w-full justify-start rounded-none border-b bg-transparent h-auto p-0">
              <TabsTrigger 
                value="all"
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-4 py-3"
              >
                All
              </TabsTrigger>
              <TabsTrigger 
                value="users"
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-4 py-3"
              >
                <Users className="h-4 w-4 mr-2" />
                People ({userResults.length})
              </TabsTrigger>
              <TabsTrigger 
                value="posts"
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-4 py-3"
              >
                <FileText className="h-4 w-4 mr-2" />
                Posts ({postResults.length})
              </TabsTrigger>
              <TabsTrigger 
                value="groups"
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-4 py-3"
              >
                <Hash className="h-4 w-4 mr-2" />
                Groups ({groupResults.length})
              </TabsTrigger>
            </TabsList>
          </Tabs>

          {/* Results */}
          <div>
            {isLoading ? (
              <div className="p-8 text-center text-muted-foreground">
                Searching...
              </div>
            ) : filteredResults.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                <SearchIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No results for "{query}"</p>
                <p className="text-sm mt-2">Try a different search term</p>
              </div>
            ) : (
              <div>
                {(activeTab === 'all' || activeTab === 'users') && userResults.length > 0 && (
                  <div>
                    {activeTab === 'all' && (
                      <h2 className="font-semibold p-4 border-b">People</h2>
                    )}
                    {userResults.map(result => (
                      <Link
                        key={result.id}
                        to={`/profile/${result.data.handle}`}
                        className="flex items-center gap-3 p-4 hover:bg-muted/50 transition border-b"
                      >
                        <Avatar>
                          <AvatarFallback>
                            {(result.data.profile?.name || result.data.handle || '?')[0].toUpperCase()}
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold truncate">
                            {result.data.profile?.name || result.data.handle}
                          </p>
                          <p className="text-sm text-muted-foreground truncate">
                            @{result.data.handle}
                          </p>
                          {result.data.profile?.bio && (
                            <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                              {result.data.profile.bio}
                            </p>
                          )}
                        </div>
                        <Button variant="outline" size="sm">
                          View
                        </Button>
                      </Link>
                    ))}
                  </div>
                )}

                {(activeTab === 'all' || activeTab === 'posts') && postResults.length > 0 && (
                  <div>
                    {activeTab === 'all' && (
                      <h2 className="font-semibold p-4 border-b">Posts</h2>
                    )}
                    {postResults.map(result => (
                      <PostCard key={result.id} post={result.data} />
                    ))}
                  </div>
                )}

                {(activeTab === 'all' || activeTab === 'groups') && groupResults.length > 0 && (
                  <div>
                    {activeTab === 'all' && (
                      <h2 className="font-semibold p-4 border-b">Groups</h2>
                    )}
                    {groupResults.map(result => (
                      <Link
                        key={result.id}
                        to={`/groups/${result.id}`}
                        className="flex items-center gap-3 p-4 hover:bg-muted/50 transition border-b"
                      >
                        <div className="h-12 w-12 rounded-lg bg-muted flex items-center justify-center">
                          <Hash className="h-6 w-6 text-muted-foreground" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold truncate">{result.data.name}</p>
                          <p className="text-sm text-muted-foreground truncate">
                            {result.data.member_count} members
                          </p>
                          {result.data.description && (
                            <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                              {result.data.description}
                            </p>
                          )}
                        </div>
                        <Button variant="outline" size="sm">
                          View
                        </Button>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      ) : (
        /* Trending / Explore */
        <div className="p-4">
          <h2 className="font-bold text-xl mb-4 flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Trending
          </h2>
          {trending.length === 0 ? (
            <p className="text-muted-foreground">No trending topics yet</p>
          ) : (
            <div className="space-y-4">
              {trending.map((topic, i) => (
                <button
                  key={topic}
                  className="w-full text-left p-3 rounded-lg hover:bg-muted transition"
                  onClick={() => {
                    setSearchQuery(topic);
                    setSearchParams({ q: topic });
                  }}
                >
                  <p className="text-sm text-muted-foreground">
                    {i + 1} · Trending
                  </p>
                  <p className="font-semibold">{topic}</p>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
