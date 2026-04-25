/**
 * Create Group Dialog
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from '@/components/ui/dialog';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { useAuth } from '@/contexts/AuthContext';
import { Plus, Loader2, Globe, Lock } from 'lucide-react';

const API_URL = '/api';

interface CreateGroupDialogProps {
  trigger?: React.ReactNode;
  onCreated?: (group: any) => void;
}

export function CreateGroupDialog({ trigger, onCreated }: CreateGroupDialogProps) {
  const navigate = useNavigate();
  const { user, token } = useAuth();
  
  const [open, setOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [access, setAccess] = useState<'public' | 'private'>('public');

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError('Group name is required');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const resp = await fetch(`${API_URL}/groups`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token,
          name: name.trim(),
          description: description.trim(),
          access,
        }),
      });

      if (!resp.ok) {
        const data = await resp.json();
        throw new Error(data.detail || 'Failed to create group');
      }

      const group = await resp.json();
      setOpen(false);
      resetForm();
      
      if (onCreated) {
        onCreated(group);
      } else {
        navigate(`/groups/${group.id}`);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to create group');
    } finally {
      setIsLoading(false);
    }
  }

  function resetForm() {
    setName('');
    setDescription('');
    setAccess('public');
    setError('');
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) resetForm(); }}>
      <DialogTrigger asChild>
        {trigger || (
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Create Group
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create a New Group</DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleCreate} className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="group-name">Group Name *</Label>
            <Input
              id="group-name"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g., Photography Enthusiasts"
              maxLength={100}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="group-description">Description</Label>
            <Textarea
              id="group-description"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="What is this group about?"
              rows={3}
              maxLength={500}
            />
            <p className="text-xs text-muted-foreground">
              {description.length}/500 characters
            </p>
          </div>

          <div className="space-y-3">
            <Label>Group Visibility</Label>
            <RadioGroup value={access} onValueChange={(v) => setAccess(v as any)}>
              <div className="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-muted/50 transition">
                <RadioGroupItem value="public" id="public" className="mt-1" />
                <label htmlFor="public" className="flex-1 cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Globe className="h-4 w-4" />
                    <span className="font-medium">Public</span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    Anyone can find and join this group
                  </p>
                </label>
              </div>
              <div className="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-muted/50 transition">
                <RadioGroupItem value="private" id="private" className="mt-1" />
                <label htmlFor="private" className="flex-1 cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Lock className="h-4 w-4" />
                    <span className="font-medium">Private</span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    Only invited members can join
                  </p>
                </label>
              </div>
            </RadioGroup>
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
              Create Group
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
