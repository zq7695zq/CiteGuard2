# 中文注释：本文件(frontend/Dockerfile)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
FROM node:20-alpine
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
