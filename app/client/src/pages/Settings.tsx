/**
 * Settings Page
 */
import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useAuth } from '@/contexts/AuthContext';
import { AppPageShell } from '@/components/AppPageShell';
import { 
  User, Bell, Shield, Palette, Key, Smartphone, 
  LogOut, Trash2, Download, Upload, Check, Loader2,
  Moon, Sun, Monitor
} from 'lucide-react';

const API_URL = '/api';

export default function Settings() {
  const { user, token, logout } = useAuth();
  
  // Profile settings
  const [name, setName] = useState(user?.profile?.name || '');
  const [bio, setBio] = useState(user?.profile?.bio || '');
  const [avatar, setAvatar] = useState(user?.profile?.avatar || '');
  
  // Notification settings
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [pushNotifications, setPushNotifications] = useState(true);
  const [notifyLikes, setNotifyLikes] = useState(true);
  const [notifyReplies, setNotifyReplies] = useState(true);
  const [notifyFollows, setNotifyFollows] = useState(true);
  const [notifyMentions, setNotifyMentions] = useState(true);
  
  // Privacy settings
  const [privateAccount, setPrivateAccount] = useState(false);
  const [showActivity, setShowActivity] = useState(true);
  const [allowDMs, setAllowDMs] = useState(true);
  
  // Appearance
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('system');
  
  // Devices
  const [devices, setDevices] = useState<any[]>([]);
  
  // State
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadDevices();
    loadSettings();
  }, []);

  async function loadSettings() {
    try {
      const resp = await fetch(`${API_URL}/settings?token=${token}`);
      if (resp.ok) {
        const data = await resp.json();
        // Apply settings...
      }
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  }

  async function loadDevices() {
    try {
      const resp = await fetch(`${API_URL}/devices?token=${token}`);
      if (resp.ok) {
        const data = await resp.json();
        setDevices(data.devices || []);
      }
    } catch (err) {
      console.error('Failed to load devices:', err);
    }
  }

  async function saveProfile() {
    setIsSaving(true);
    try {
      const resp = await fetch(`${API_URL}/entities/${user?.entityId}?token=${token}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile: { name, bio, avatar }
        }),
      });
      if (resp.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      }
    } catch (err) {
      console.error('Failed to save profile:', err);
    } finally {
      setIsSaving(false);
    }
  }

  async function revokeDevice(deviceId: string) {
    try {
      await fetch(`${API_URL}/devices/${deviceId}?token=${token}`, {
        method: 'DELETE',
      });
      setDevices(prev => prev.filter(d => d.id !== deviceId));
    } catch (err) {
      console.error('Failed to revoke device:', err);
    }
  }

  async function exportData() {
    try {
      const resp = await fetch(`${API_URL}/export?token=${token}`);
      if (resp.ok) {
        const data = await resp.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `mesh-export-${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error('Failed to export data:', err);
    }
  }

  function handleThemeChange(newTheme: 'light' | 'dark' | 'system') {
    setTheme(newTheme);
    if (newTheme === 'dark') {
      document.documentElement.classList.add('dark');
    } else if (newTheme === 'light') {
      document.documentElement.classList.remove('dark');
    } else {
      // System preference
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }
    localStorage.setItem('theme', newTheme);
  }

  return (
    <AppPageShell>
    <div className="mx-auto w-full max-w-2xl p-4">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>
      
      <Tabs defaultValue="profile">
        <TabsList className="mb-6">
          <TabsTrigger value="profile">
            <User className="h-4 w-4 mr-2" />
            Profile
          </TabsTrigger>
          <TabsTrigger value="notifications">
            <Bell className="h-4 w-4 mr-2" />
            Notifications
          </TabsTrigger>
          <TabsTrigger value="privacy">
            <Shield className="h-4 w-4 mr-2" />
            Privacy
          </TabsTrigger>
          <TabsTrigger value="appearance">
            <Palette className="h-4 w-4 mr-2" />
            Appearance
          </TabsTrigger>
          <TabsTrigger value="security">
            <Key className="h-4 w-4 mr-2" />
            Security
          </TabsTrigger>
        </TabsList>

        {/* Profile Tab */}
        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
              <CardDescription>Update your public profile information</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center gap-4">
                <Avatar className="h-20 w-20">
                  {avatar && <AvatarImage src={avatar} />}
                  <AvatarFallback className="text-2xl">
                    {(name || user?.handle || '?')[0].toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <Button variant="outline" size="sm">
                    <Upload className="h-4 w-4 mr-2" />
                    Upload Photo
                  </Button>
                  <p className="text-sm text-muted-foreground mt-1">
                    JPG, PNG, GIF. Max 2MB.
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="name">Display Name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Your name"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="handle">Handle</Label>
                <Input
                  id="handle"
                  value={`@${user?.handle || ''}`}
                  disabled
                  className="bg-muted"
                />
                <p className="text-sm text-muted-foreground">
                  Your handle cannot be changed
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="bio">Bio</Label>
                <Textarea
                  id="bio"
                  value={bio}
                  onChange={e => setBio(e.target.value)}
                  placeholder="Tell people about yourself..."
                  rows={3}
                />
              </div>

              <Button onClick={saveProfile} disabled={isSaving}>
                {isSaving ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : saved ? (
                  <Check className="h-4 w-4 mr-2" />
                ) : null}
                {saved ? 'Saved!' : 'Save Changes'}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Notifications Tab */}
        <TabsContent value="notifications">
          <Card>
            <CardHeader>
              <CardTitle>Notification Preferences</CardTitle>
              <CardDescription>Control how you receive notifications</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Email Notifications</p>
                  <p className="text-sm text-muted-foreground">
                    Receive notifications via email
                  </p>
                </div>
                <Switch
                  checked={emailNotifications}
                  onCheckedChange={setEmailNotifications}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Push Notifications</p>
                  <p className="text-sm text-muted-foreground">
                    Receive push notifications in browser
                  </p>
                </div>
                <Switch
                  checked={pushNotifications}
                  onCheckedChange={setPushNotifications}
                />
              </div>

              <hr />

              <p className="font-medium">Notify me about:</p>

              <div className="space-y-4 pl-4">
                <div className="flex items-center justify-between">
                  <p>Likes on my posts</p>
                  <Switch checked={notifyLikes} onCheckedChange={setNotifyLikes} />
                </div>
                <div className="flex items-center justify-between">
                  <p>Replies to my posts</p>
                  <Switch checked={notifyReplies} onCheckedChange={setNotifyReplies} />
                </div>
                <div className="flex items-center justify-between">
                  <p>New followers</p>
                  <Switch checked={notifyFollows} onCheckedChange={setNotifyFollows} />
                </div>
                <div className="flex items-center justify-between">
                  <p>Mentions</p>
                  <Switch checked={notifyMentions} onCheckedChange={setNotifyMentions} />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Privacy Tab */}
        <TabsContent value="privacy">
          <Card>
            <CardHeader>
              <CardTitle>Privacy Settings</CardTitle>
              <CardDescription>Control who can see your content</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Private Account</p>
                  <p className="text-sm text-muted-foreground">
                    Only approved followers can see your posts
                  </p>
                </div>
                <Switch
                  checked={privateAccount}
                  onCheckedChange={setPrivateAccount}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Show Activity Status</p>
                  <p className="text-sm text-muted-foreground">
                    Let others see when you're online
                  </p>
                </div>
                <Switch
                  checked={showActivity}
                  onCheckedChange={setShowActivity}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Allow Direct Messages</p>
                  <p className="text-sm text-muted-foreground">
                    Let anyone send you messages
                  </p>
                </div>
                <Switch
                  checked={allowDMs}
                  onCheckedChange={setAllowDMs}
                />
              </div>

              <hr />

              <div>
                <Button variant="outline" onClick={exportData}>
                  <Download className="h-4 w-4 mr-2" />
                  Export Your Data
                </Button>
                <p className="text-sm text-muted-foreground mt-2">
                  Download all your posts, followers, and account data
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Appearance Tab */}
        <TabsContent value="appearance">
          <Card>
            <CardHeader>
              <CardTitle>Appearance</CardTitle>
              <CardDescription>Customize how MESH looks</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <p className="font-medium mb-4">Theme</p>
                <div className="grid grid-cols-3 gap-4">
                  <button
                    className={`p-4 border rounded-lg flex flex-col items-center gap-2 transition ${
                      theme === 'light' ? 'border-primary bg-primary/5' : 'hover:bg-muted'
                    }`}
                    onClick={() => handleThemeChange('light')}
                  >
                    <Sun className="h-6 w-6" />
                    <span className="text-sm">Light</span>
                  </button>
                  <button
                    className={`p-4 border rounded-lg flex flex-col items-center gap-2 transition ${
                      theme === 'dark' ? 'border-primary bg-primary/5' : 'hover:bg-muted'
                    }`}
                    onClick={() => handleThemeChange('dark')}
                  >
                    <Moon className="h-6 w-6" />
                    <span className="text-sm">Dark</span>
                  </button>
                  <button
                    className={`p-4 border rounded-lg flex flex-col items-center gap-2 transition ${
                      theme === 'system' ? 'border-primary bg-primary/5' : 'hover:bg-muted'
                    }`}
                    onClick={() => handleThemeChange('system')}
                  >
                    <Monitor className="h-6 w-6" />
                    <span className="text-sm">System</span>
                  </button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security Tab */}
        <TabsContent value="security">
          <Card>
            <CardHeader>
              <CardTitle>Security</CardTitle>
              <CardDescription>Manage your account security</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <p className="font-medium mb-4 flex items-center gap-2">
                  <Smartphone className="h-4 w-4" />
                  Logged in Devices
                </p>
                {devices.length === 0 ? (
                  <p className="text-muted-foreground">No devices found</p>
                ) : (
                  <div className="space-y-4">
                    {devices.map(device => (
                      <div 
                        key={device.id} 
                        className="flex items-center justify-between p-3 border rounded-lg"
                      >
                        <div>
                          <p className="font-medium">{device.device_name}</p>
                          <p className="text-sm text-muted-foreground">
                            Last active: {new Date(device.last_used_at).toLocaleDateString()}
                          </p>
                        </div>
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => revokeDevice(device.id)}
                        >
                          Revoke
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <hr />

              <div>
                <Button variant="outline" className="text-destructive hover:text-destructive">
                  <LogOut className="h-4 w-4 mr-2" />
                  Log Out All Devices
                </Button>
              </div>

              <hr />

              <div>
                <p className="font-medium text-destructive mb-2">Danger Zone</p>
                <Button variant="destructive">
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete Account
                </Button>
                <p className="text-sm text-muted-foreground mt-2">
                  This action cannot be undone
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
    </AppPageShell>
  );
}
