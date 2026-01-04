// 中文注释：本文件(frontend/src/main.tsx)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
