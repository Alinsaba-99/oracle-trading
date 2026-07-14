import { createBrowserRouter, Link } from 'react-router-dom'
import { Layout } from '@/routes/layout'
import DashboardPage from '@/routes/dashboard-page'
import TradesPage from '@/routes/trades-page'
import GaPage from '@/routes/ga-page'

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <h2 className="text-xl font-semibold mb-2">Page not found</h2>
      <p className="text-sm text-muted-foreground mb-4">
        The page you're looking for doesn't exist.
      </p>
      <Link
        to="/"
        className="px-4 py-2 text-sm rounded-md bg-accent text-accent-foreground hover:bg-accent/80 transition-colors"
      >
        Go to Dashboard
      </Link>
    </div>
  )
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'trades', element: <TradesPage /> },
      { path: 'ga', element: <GaPage /> },
      { path: '*', element: <NotFound /> },
    ],
  },
])
