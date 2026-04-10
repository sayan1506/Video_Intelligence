import { useState, useEffect } from 'react'
import { healthCheck } from '../services/api'

export default function UploadPage() {
  const [apiStatus, setApiStatus] = useState('checking...')
  const [corsOk, setCorsOk] = useState(null)

  useEffect(() => {
    async function testConnectivity() {
      try {
        const health = await healthCheck()
        setApiStatus(`${health.status} — ${health.service}`)
        setCorsOk(true)
      } catch (err) {
        if (err.message.includes('Network Error') || err.message.includes('CORS')) {
          setApiStatus('CORS error — check backend allow_origins')
          setCorsOk(false)
        } else {
          setApiStatus(`Error: ${err.message}`)
          setCorsOk(false)
        }
        console.error('API connectivity test failed:', err)
      }
    }
    testConnectivity()
  }, [])

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">VidIQ</h1>
        <div className={`text-sm px-3 py-2 rounded-full inline-block ${
          corsOk === true ? 'bg-green-100 text-green-800' :
          corsOk === false ? 'bg-red-100 text-red-800' :
          'bg-gray-100 text-gray-600'
        }`}>
          API: {apiStatus}
        </div>
        <p className="text-gray-400 text-xs mt-3">
          Remove this connectivity test in Week 5 Day 1
        </p>
      </div>
    </div>
  )
}
