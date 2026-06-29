import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import LandingPage from './pages/LandingPage'
import UploadPage from './pages/UploadPage'
import StatusPage from './pages/StatusPage'
import ResultPage from './pages/ResultPage'
import DashboardPage from './pages/DashboardPage'
import PricingPage from './pages/PricingPage'
import BillingSuccessPage from './pages/BillingSuccessPage'
import AdminDashboard from './pages/AdminDashboard'
import SharePage from './pages/SharePage'
import ComingSoonPage from './components/ComingSoonPage'

// Set to false to re-enable the full app.
const COMING_SOON = true

/**
 * PrivateRoute — redirects unauthenticated users to the landing page.
 *
 * Shows nothing while the initial auth state is loading (avoids a flash
 * of the landing page for already-signed-in users on hard refresh).
 */
function PrivateRoute({ children }) {
  const { user, loading } = useAuth()

  if (loading) {
    // Minimal full-screen spinner — matches the dark theme
    return (
      <div className="min-h-screen bg-gold-light-bg-primary dark:bg-gold-bg-primary flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-gold-light-accent dark:border-gold-accent border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/" replace />
  }

  return children
}

function App() {
  if (COMING_SOON) {
    return <ComingSoonPage />
  }

  return (
    <BrowserRouter>
      <Routes>
        {/* Public */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/pricing" element={<PricingPage />} />
        <Route path="/billing/success" element={<BillingSuccessPage />} />
        <Route path="/share/:jobId" element={<SharePage />} />

        {/* Protected */}
        <Route path="/dashboard" element={<PrivateRoute><DashboardPage /></PrivateRoute>} />
        <Route path="/upload"    element={<PrivateRoute><UploadPage /></PrivateRoute>} />
        <Route path="/status/:jobId" element={<PrivateRoute><StatusPage /></PrivateRoute>} />
        <Route path="/result/:jobId" element={<PrivateRoute><ResultPage /></PrivateRoute>} />

        {/* Admin — UID-gated on the client, 403-gated on the server */}
        <Route path="/admin" element={<PrivateRoute><AdminDashboard /></PrivateRoute>} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
