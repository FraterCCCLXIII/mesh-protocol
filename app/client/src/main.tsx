import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

console.log('MESH Client starting...');

try {
  const root = document.getElementById('root');
  if (!root) {
    throw new Error('Root element not found');
  }
  console.log('Found root element, rendering app...');
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
  console.log('App rendered successfully');
} catch (err) {
  console.error('Failed to render app:', err);
}
