/**
 * Edit Profile Dialog
 */
import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from '@/components/ui/dialog';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useAuth } from '@/contexts/AuthContext';
import { Pencil, Loader2, Camera } from 'lucide-react';

const API_URL = '/api';

interface EditProfileDialogProps {
  trigger?: React.ReactNode;
  onUpdated?: () => void;
}

export function EditProfileDialog({ trigger, onUpdated }: EditProfileDialogProps) {
  const { user, token } = useAuth();
  
  const [open, setOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  
  const [name, setName] = useState('');
  const [bio, setBio] = useState('');
  const [location, setLocation] = useState('');
  const [website, setWebsite] = useState('');
  const [avatar, setAvatar] = useState('');

  useEffect(() => {
    if (open && user) {
      setName(user.profile?.name || '');
      setBio(user.profile?.bio || '');
      setLocation(user.profile?.location || '');
      setWebsite(user.profile?.website || '');
      setAvatar(user.profile?.avatar || '');
    }
  }, [open, user]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError('Display name is required');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const resp = await fetch(`${API_URL}/entities/${user?.entityId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token,
          profile: {
            name: name.trim(),
            bio: bio.trim(),
            location: location.trim(),
            website: website.trim(),
            avatar,
          },
        }),
      });

      if (!resp.ok) {
        const data = await resp.json();
        throw new Error(data.detail || 'Failed to update profile');
      }

      setOpen(false);
      if (onUpdated) {
        onUpdated();
      }
      // Refresh page to show updated profile
      window.location.reload();
    } catch (err: any) {
      setError(err.message || 'Failed to update profile');
    } finally {
      setIsLoading(false);
    }
  }

  function handleAvatarUpload() {
    // For now, prompt for URL. In production, this would open a file picker
    const url = prompt('Enter avatar URL:');
    if (url) {
      setAvatar(url);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="outline">
            <Pencil className="h-4 w-4 mr-2" />
            Edit Profile
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit Profile</DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSave} className="space-y-6">
          {/* Avatar */}
          <div className="flex flex-col items-center gap-4">
            <div className="relative">
              <Avatar className="h-24 w-24">
                {avatar && <AvatarImage src={avatar} />}
                <AvatarFallback className="text-2xl">
                  {(name || user?.handle || '?')[0].toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <button
                type="button"
                onClick={handleAvatarUpload}
                className="absolute bottom-0 right-0 p-2 bg-primary text-primary-foreground rounded-full shadow-lg hover:bg-primary/90 transition"
              >
                <Camera className="h-4 w-4" />
              </button>
            </div>
            <p className="text-sm text-muted-foreground">
              Click the camera icon to change your photo
            </p>
          </div>

          {/* Name */}
          <div className="space-y-2">
            <Label htmlFor="profile-name">Display Name *</Label>
            <Input
              id="profile-name"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Your name"
              maxLength={50}
            />
          </div>

          {/* Bio */}
          <div className="space-y-2">
            <Label htmlFor="profile-bio">Bio</Label>
            <Textarea
              id="profile-bio"
              value={bio}
              onChange={e => setBio(e.target.value)}
              placeholder="Tell people about yourself..."
              rows={3}
              maxLength={160}
            />
            <p className="text-xs text-muted-foreground text-right">
              {bio.length}/160
            </p>
          </div>

          {/* Location */}
          <div className="space-y-2">
            <Label htmlFor="profile-location">Location</Label>
            <Input
              id="profile-location"
              value={location}
              onChange={e => setLocation(e.target.value)}
              placeholder="Where are you based?"
              maxLength={30}
            />
          </div>

          {/* Website */}
          <div className="space-y-2">
            <Label htmlFor="profile-website">Website</Label>
            <Input
              id="profile-website"
              type="url"
              value={website}
              onChange={e => setWebsite(e.target.value)}
              placeholder="https://yourwebsite.com"
            />
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading || !name.trim()}>
              {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
