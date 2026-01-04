// 中文注释：本文件(frontend/src/components/TasksTable.tsx)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
interface TaskItem {
  id: string
  type: string
  key: string
  status: string
  attempt: number
  error?: any
}

export default function TasksTable({ title, tasks, onRetry, onSkip }: {
  title: string
  tasks: TaskItem[]
  onRetry: (taskId: string) => void
  onSkip: (taskId: string) => void
}) {
  return (
    <div style={{ marginBottom: 16 }}>
      <h3>{title}</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>Key</th>
            <th>Status</th>
            <th>Attempt</th>
            <th>Error</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <tr key={task.id}>
              <td>{task.key}</td>
              <td>{task.status}</td>
              <td>{task.attempt}</td>
              <td>{task.error?.message || '-'}</td>
              <td>
                <button onClick={() => onRetry(task.id)}>Retry</button>
                <button onClick={() => onSkip(task.id)} style={{ marginLeft: 8 }}>Skip</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
