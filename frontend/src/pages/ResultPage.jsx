import { useParams } from 'react-router-dom'

export default function ResultPage() {
  const { jobId } = useParams()
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <p className="text-gray-500">Results for job: {jobId}</p>
        <p className="text-gray-400 text-sm mt-1">Result page — Week 5 Day 3+</p>
      </div>
    </div>
  )
}