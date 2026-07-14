import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { router } from '@/routes'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { PageShell } from '@/components/ui/page-shell'
import { ThemeProvider } from '@/hooks/use-theme'
import '@/index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary
      fallback={
        <div className="flex items-center justify-center h-screen bg-background">
          <PageShell title="Application Error" description="Something went wrong. Try refreshing the page.">
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 text-sm rounded-md bg-accent text-accent-foreground hover:bg-accent/80 transition-colors"
            >
              Refresh
            </button>
          </PageShell>
        </div>
      }
    >
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </ThemeProvider>
    </ErrorBoundary>
  </React.StrictMode>,
)
