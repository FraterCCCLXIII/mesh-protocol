/**
 * Media Upload Component
 */
import { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import { Image, X, Loader2, Film, AlertCircle } from 'lucide-react';

const MEDIA_API = '/api/media';
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'video/mp4'];

interface MediaUploadProps {
  onUpload: (urls: string[]) => void;
  maxFiles?: number;
}

interface UploadedMedia {
  id: string;
  url: string;
  type: 'image' | 'video';
  status: 'uploading' | 'done' | 'error';
}

export function MediaUpload({ onUpload, maxFiles = 4 }: MediaUploadProps) {
  const { token } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [media, setMedia] = useState<UploadedMedia[]>([]);
  const [error, setError] = useState('');

  function handleClick() {
    fileInputRef.current?.click();
  }

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setError('');

    // Check max files
    if (media.length + files.length > maxFiles) {
      setError(`Maximum ${maxFiles} files allowed`);
      return;
    }

    for (const file of Array.from(files)) {
      // Validate file type
      if (!ALLOWED_TYPES.includes(file.type)) {
        setError('Only images and videos are allowed');
        continue;
      }

      // Validate file size
      if (file.size > MAX_FILE_SIZE) {
        setError('File too large (max 10MB)');
        continue;
      }

      await uploadFile(file);
    }

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }

  async function uploadFile(file: File) {
    const tempId = `temp-${Date.now()}-${Math.random()}`;
    const isVideo = file.type.startsWith('video/');

    // Add placeholder
    setMedia(prev => [...prev, {
      id: tempId,
      url: URL.createObjectURL(file),
      type: isVideo ? 'video' : 'image',
      status: 'uploading',
    }]);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('token', token || '');

      const resp = await fetch(`${MEDIA_API}/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!resp.ok) {
        throw new Error('Upload failed');
      }

      const data = await resp.json();

      // Update with real URL
      setMedia(prev => prev.map(m => 
        m.id === tempId 
          ? { ...m, id: data.id, url: data.url, status: 'done' }
          : m
      ));

      // Notify parent
      const allUrls = media
        .filter(m => m.status === 'done')
        .map(m => m.url)
        .concat(data.url);
      onUpload(allUrls);

    } catch (err) {
      setMedia(prev => prev.map(m => 
        m.id === tempId ? { ...m, status: 'error' } : m
      ));
      setError('Failed to upload file');
    }
  }

  function removeMedia(id: string) {
    setMedia(prev => prev.filter(m => m.id !== id));
    
    // Notify parent of updated URLs
    const remainingUrls = media
      .filter(m => m.id !== id && m.status === 'done')
      .map(m => m.url);
    onUpload(remainingUrls);
  }

  return (
    <div className="space-y-3">
      <input
        ref={fileInputRef}
        type="file"
        accept={ALLOWED_TYPES.join(',')}
        multiple
        className="hidden"
        onChange={handleFileSelect}
      />

      {/* Media Grid */}
      {media.length > 0 && (
        <div className={`grid gap-2 ${
          media.length === 1 ? 'grid-cols-1' : 
          media.length === 2 ? 'grid-cols-2' :
          media.length === 3 ? 'grid-cols-2' : 'grid-cols-2'
        }`}>
          {media.map((item, index) => (
            <div 
              key={item.id} 
              className={`relative rounded-lg overflow-hidden bg-muted ${
                media.length === 3 && index === 0 ? 'row-span-2' : ''
              }`}
            >
              {item.type === 'image' ? (
                <img 
                  src={item.url} 
                  alt="" 
                  className="w-full h-full object-cover aspect-square"
                />
              ) : (
                <video 
                  src={item.url} 
                  className="w-full h-full object-cover aspect-square"
                />
              )}

              {/* Status Overlay */}
              {item.status === 'uploading' && (
                <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                  <Loader2 className="h-8 w-8 text-white animate-spin" />
                </div>
              )}

              {item.status === 'error' && (
                <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                  <AlertCircle className="h-8 w-8 text-destructive" />
                </div>
              )}

              {/* Remove Button */}
              <button
                type="button"
                onClick={() => removeMedia(item.id)}
                className="absolute top-2 right-2 p-1 bg-black/50 rounded-full hover:bg-black/70 transition"
              >
                <X className="h-4 w-4 text-white" />
              </button>

              {/* Video indicator */}
              {item.type === 'video' && (
                <div className="absolute bottom-2 left-2 p-1 bg-black/50 rounded">
                  <Film className="h-4 w-4 text-white" />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      {/* Upload Button */}
      {media.length < maxFiles && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleClick}
        >
          <Image className="h-4 w-4 mr-2" />
          Add Photo/Video
        </Button>
      )}
    </div>
  );
}
