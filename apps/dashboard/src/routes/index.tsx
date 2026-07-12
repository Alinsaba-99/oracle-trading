import { createBrowserRouter } from 'react-router-dom'
import { Layout } from '@/routes/layout'
import DashboardPage from '@/routes/dashboard-page'
import TradesPage from '@/routes/trades-page'
import GaPage from '@/routes/ga-page'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'trades', element: <TradesPage /> },
      { path: 'ga', element: <GaPage /> },
    ],
  },
])
