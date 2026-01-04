// 中文注释：本文件(frontend/src/App.tsx)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
import { Routes, Route, Link } from 'react-router-dom'
import JobsList from './pages/JobsList'
import JobDetail from './pages/JobDetail'

export default function App() {
  return (
    <div style={{ padding: 16, fontFamily: 'sans-serif' }}>
      <header style={{ marginBottom: 16 }}>
        <Link to="/jobs" style={{ fontWeight: 700 }}>
          CiteGuard2
        </Link>
      </header>
      <Routes>
        <Route path="/jobs" element={<JobsList />} />
        <Route path="/jobs/:id" element={<JobDetail />} />
      </Routes>
    </div>
  )
}
