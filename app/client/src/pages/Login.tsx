/**
 * Login/Register Page — Identity Vault (default) or local dev keys (VITE_IDENTITY_MODE=local).
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Label } from '@/components/ui/label';
import { isLocalIdentityMode } from '@/config/identityMode';
import { useAuth } from '@/contexts/AuthContext';
import { loginLocalIdentity, registerLocalIdentity } from '@/lib/localIdentity';
import { Loader2, Mail, Lock, User, AtSign } from 'lucide-react';

export default function Login() {
  const navigate = useNavigate();
  const { login, register, isLoading } = useAuth();
  
  const [tab, setTab] = useState('login');
  const [error, setError] = useState('');
  
  // Login form
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  
  // Register form
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regHandle, setRegHandle] = useState('');
  const [regName, setRegName] = useState('');

  // Local dev identity (no vault)
  const [localName, setLocalName] = useState('');
  const [localHandle, setLocalHandle] = useState('');
  const [localLoading, setLocalLoading] = useState(false);
  const [localError, setLocalError] = useState('');

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await login(loginEmail, loginPassword);
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Login failed');
    }
  }
  
  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await register(regEmail, regPassword, regHandle, regName);
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Registration failed');
    }
  }

  async function handleLocalRegister(e: React.FormEvent) {
    e.preventDefault();
    setLocalError('');
    setLocalLoading(true);
    try {
      await registerLocalIdentity(localHandle, localName);
      window.location.assign('/');
    } catch (err: unknown) {
      setLocalError(err instanceof Error ? err.message : 'Local registration failed');
    } finally {
      setLocalLoading(false);
    }
  }

  async function handleLocalLogin(e: React.FormEvent) {
    e.preventDefault();
    setLocalError('');
    setLocalLoading(true);
    try {
      await loginLocalIdentity();
      window.location.assign('/');
    } catch (err: unknown) {
      setLocalError(err instanceof Error ? err.message : 'Local login failed');
    } finally {
      setLocalLoading(false);
    }
  }

  if (isLocalIdentityMode()) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold">MESH (local dev)</CardTitle>
            <CardDescription>
              In-browser keys only. Set VITE_IDENTITY_MODE=local. No Identity Vault, no recovery.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <form onSubmit={handleLocalRegister} className="space-y-3">
              <p className="text-sm font-medium">Create local account</p>
              <Input
                placeholder="Display name"
                value={localName}
                onChange={(e) => setLocalName(e.target.value)}
                required
              />
              <Input
                placeholder="Handle (a-z, 0-9, _)"
                value={localHandle}
                onChange={(e) =>
                  setLocalHandle(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))
                }
                required
              />
              <Button type="submit" className="w-full" disabled={localLoading}>
                {localLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Create local account
              </Button>
            </form>
            <form onSubmit={handleLocalLogin} className="space-y-3 border-t pt-4">
              <p className="text-sm font-medium">Sign in with saved local keys</p>
              <Button type="submit" variant="secondary" className="w-full" disabled={localLoading}>
                Continue with local keys
              </Button>
            </form>
            {localError && <p className="text-sm text-red-500">{localError}</p>}
          </CardContent>
          <CardFooter className="text-xs text-zinc-500 text-center block">
            See docs/IDENTITY.md for the Vault (recommended) and recovery.
          </CardFooter>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold">MESH</CardTitle>
          <CardDescription>Decentralized Social Network</CardDescription>
        </CardHeader>
        
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="login">Login</TabsTrigger>
            <TabsTrigger value="register">Register</TabsTrigger>
          </TabsList>
          
          <TabsContent value="login">
            <form onSubmit={handleLogin}>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="login-email">Email</Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-3 h-4 w-4 text-zinc-400" />
                    <Input
                      id="login-email"
                      type="email"
                      placeholder="you@example.com"
                      className="pl-9"
                      value={loginEmail}
                      onChange={e => setLoginEmail(e.target.value)}
                      required
                    />
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="login-password">Password</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-3 h-4 w-4 text-zinc-400" />
                    <Input
                      id="login-password"
                      type="password"
                      placeholder="••••••••"
                      className="pl-9"
                      value={loginPassword}
                      onChange={e => setLoginPassword(e.target.value)}
                      required
                    />
                  </div>
                </div>
                
                {error && <p className="text-sm text-red-500">{error}</p>}
              </CardContent>
              
              <CardFooter>
                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Sign In
                </Button>
              </CardFooter>
            </form>
          </TabsContent>
          
          <TabsContent value="register">
            <form onSubmit={handleRegister}>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="reg-name">Display Name</Label>
                  <div className="relative">
                    <User className="absolute left-3 top-3 h-4 w-4 text-zinc-400" />
                    <Input
                      id="reg-name"
                      type="text"
                      placeholder="Your Name"
                      className="pl-9"
                      value={regName}
                      onChange={e => setRegName(e.target.value)}
                      required
                    />
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="reg-handle">Handle</Label>
                  <div className="relative">
                    <AtSign className="absolute left-3 top-3 h-4 w-4 text-zinc-400" />
                    <Input
                      id="reg-handle"
                      type="text"
                      placeholder="username"
                      className="pl-9"
                      value={regHandle}
                      onChange={e => setRegHandle(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                      required
                    />
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="reg-email">Email</Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-3 h-4 w-4 text-zinc-400" />
                    <Input
                      id="reg-email"
                      type="email"
                      placeholder="you@example.com"
                      className="pl-9"
                      value={regEmail}
                      onChange={e => setRegEmail(e.target.value)}
                      required
                    />
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="reg-password">Password</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-3 h-4 w-4 text-zinc-400" />
                    <Input
                      id="reg-password"
                      type="password"
                      placeholder="••••••••"
                      className="pl-9"
                      value={regPassword}
                      onChange={e => setRegPassword(e.target.value)}
                      minLength={8}
                      required
                    />
                  </div>
                  <p className="text-xs text-zinc-500">Minimum 8 characters</p>
                </div>
                
                {error && <p className="text-sm text-red-500">{error}</p>}
              </CardContent>
              
              <CardFooter>
                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Create Account
                </Button>
              </CardFooter>
            </form>
          </TabsContent>
        </Tabs>
        
        <div className="p-4 text-center text-sm text-zinc-500 border-t">
          <p>Your keys are encrypted client-side.</p>
          <p>We never see your private keys.</p>
        </div>
      </Card>
    </div>
  );
}
