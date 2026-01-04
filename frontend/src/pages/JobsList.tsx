// 中文注释：本文件(frontend/src/pages/JobsList.tsx)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
import { useEffect, useState } from 'react'
import { createJob, fetchJobs } from '../api/client'
import { Link } from 'react-router-dom'

interface JobItem {
  job_id: string
  status: string
  stage: string
  progress: { done?: number; total?: number }
  created_at: string
}

export default function JobsList() {
  const [jobs, setJobs] = useState<JobItem[]>([])
  const [paperText, setPaperText] = useState('')
  const [bibText, setBibText] = useState('')

  const loadJobs = async () => {
    setJobs(await fetchJobs())
  }

  useEffect(() => {
    loadJobs()
  }, [])

  const onSubmit = async () => {
    await createJob(paperText, bibText)
    setPaperText('')
    setBibText('')
    await loadJobs()
  }

  return (
    <div>
      <h2>Jobs</h2>
      <div style={{ marginBottom: 16 }}>
        <textarea
          placeholder="paper text"
          value={paperText}
          onChange={(e) => setPaperText(e.target.value)}
          rows={4}
          style={{ width: '100%' }}
        />
        <textarea
          placeholder="bib text"
          value={bibText}
          onChange={(e) => setBibText(e.target.value)}
          rows={4}
          style={{ width: '100%', marginTop: 8 }}
        />
        <button onClick={onSubmit} style={{ marginTop: 8 }}>Create Job</button>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th>ID</th>
            <th>Status</th>
            <th>Stage</th>
            <th>Progress</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.job_id}>
              <td>{job.job_id}</td>
              <td>{job.status}</td>
              <td>{job.stage}</td>
              <td>
                {job.progress?.done ?? 0}/{job.progress?.total ?? 0}
              </td>
              <td>
                <Link to={`/jobs/${job.job_id}`}>Details</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
