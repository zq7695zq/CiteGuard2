// 中文注释：本文件(frontend/src/components/EventStream.tsx)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
// 中文注释：事件流组件，订阅 SSE 并支持按类型/级别筛选展示。
import { useEffect, useState } from 'react'
import { openEventSource } from '../api/client'

interface EventItem {
  seq: number
  ts: string
  type: string
  level: string
  data: any
}

export default function EventStream({ jobId }: { jobId: string }) {
  const [events, setEvents] = useState<EventItem[]>([])
  const [filter, setFilter] = useState<'ALL' | 'ERROR' | 'TOOL' | 'LLM'>('ALL')

  useEffect(() => {
    let lastSeq = 0
    const source = openEventSource(jobId, lastSeq, (event) => {
      lastSeq = event.seq
      setEvents((prev) => [event, ...prev].slice(0, 100))
    })
    return () => source.close()
  }, [jobId])

  const filtered = events.filter((event) => {
    if (filter === 'ERROR') return event.level === 'error'
    if (filter === 'TOOL') return event.type.startsWith('tool')
    if (filter === 'LLM') return event.type.startsWith('llm')
    return true
  })

  return (
    <div style={{ border: '1px solid #ddd', padding: 8, height: 320, overflow: 'auto' }}>
      <div style={{ marginBottom: 8 }}>
        <label>Filter:</label>
        <select value={filter} onChange={(e) => setFilter(e.target.value as any)} style={{ marginLeft: 8 }}>
          <option value=\"ALL\">ALL</option>
          <option value=\"ERROR\">ERROR</option>
          <option value=\"TOOL\">TOOL</option>
          <option value=\"LLM\">LLM</option>
        </select>
      </div>
      {filtered.map((event) => (
        <div key={event.seq} style={{ marginBottom: 8 }}>
          <strong>{event.type}</strong> <small>{event.ts}</small>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(event.data, null, 2)}</pre>
        </div>
      ))}
    </div>
  )
}
