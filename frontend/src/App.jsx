import { BrowserRouter, Routes, Route } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import UploadPage from './pages/UploadPage'
import StatusPage from './pages/StatusPage'
import ResultPage from './pages/ResultPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/status/:jobId" element={<StatusPage />} />
        <Route path="/result/:jobId" element={<ResultPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App