import { useParams } from 'react-router-dom'

export default function StatusPage() {
  const { jobId } = useParams()
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <p className="text-gray-500">Processing job: {jobId}</p>
        <p className="text-gray-400 text-sm mt-1">Status page — Week 5 Day 2</p>
      </div>
    </div>
  )
}