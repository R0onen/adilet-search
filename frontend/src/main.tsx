import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './i18n';
import './styles.css';
import { apiMode } from './api/client';

async function start() {
  if (apiMode === 'mock') {
    const { worker } = await import('./mocks/browser');
    await worker.start({ onUnhandledRequest: 'bypass', quiet: true });
  }
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false, staleTime: 60_000 } },
  });
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <QueryClientProvider client={client}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </React.StrictMode>,
  );
}
start().catch((error) => {
  const root = document.getElementById('root');
  if (root)
    root.textContent = `Application failed to start: ${error instanceof Error ? error.message : String(error)}. Reload on http://127.0.0.1:5173.`;
});
