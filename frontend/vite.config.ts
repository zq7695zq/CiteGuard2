// 中文注释：本文件(frontend/vite.config.ts)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
})
