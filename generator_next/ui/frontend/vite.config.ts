import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite 설정: React 플러그인 + API 프록시
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0', // Docker 컨테이너에서 외부 접근 허용
    proxy: {
      // /api/* 요청을 FastAPI 백엔드로 프록시
      // Docker: VITE_API_TARGET=http://backend:8000, 로컬: localhost:8000
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            console.error('[프록시 오류]', err.message)
          })
        },
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
