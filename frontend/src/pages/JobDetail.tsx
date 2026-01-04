// 中文注释：本文件(frontend/src/pages/JobDetail.tsx)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
// 中文注释：任务详情页，包含状态、操作按钮、事件流与任务表格。
import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { fetchJob, fetchTasks, retryTasks, skipTasks, pauseJob, resumeJob, cancelJob } from '../api/client'
import EventStream from '../components/EventStream'
import TasksTable from '../components/TasksTable'

export default function JobDetail() {
  const { id } = useParams()
  const jobId = id || ''
  const [job, setJob] = useState<any>(null)
  const [tasks, setTasks] = useState<any[]>([])

  useEffect(() => {
    const load = async () => {
      if (!jobId) return
      setJob(await fetchJob(jobId))
      setTasks(await fetchTasks(jobId))
    }
    load()
    const interval = setInterval(load, 4000)
    return () => clearInterval(interval)
  }, [jobId])

  const bibTasks = useMemo(() => tasks.filter((t) => t.type === 'BIB_VERIFY'), [tasks])
  const occTasks = useMemo(() => tasks.filter((t) => t.type === 'OCC_MATCH'), [tasks])

  const onRetry = async (taskId: string) => {
    await retryTasks(jobId, [taskId])
    setTasks(await fetchTasks(jobId))
  }

  const onSkip = async (taskId: string) => {
    await skipTasks(jobId, [taskId])
    setTasks(await fetchTasks(jobId))
  }

  if (!job) return <div>Loading...</div>

  return (
    <div>
      <h2>Job {job.job_id}</h2>
      <div>Stage: {job.stage}</div>
      <div>Status: {job.status}</div>
      <div style={{ marginTop: 8 }}>
        <button onClick={() => pauseJob(jobId)}>Pause</button>
        <button onClick={() => resumeJob(jobId)} style={{ marginLeft: 8 }}>Resume</button>
        <button onClick={() => cancelJob(jobId)} style={{ marginLeft: 8 }}>Cancel</button>
      </div>
      <div style={{ margin: '16px 0' }}>
        <EventStream jobId={jobId} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <TasksTable title="Bib Tasks" tasks={bibTasks} onRetry={onRetry} onSkip={onSkip} />
        <TasksTable title="Occurrence Tasks" tasks={occTasks} onRetry={onRetry} onSkip={onSkip} />
      </div>
    </div>
  )
}
