// ============================================================
// React 진입점
// ============================================================

import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/globals.css'

const rootEl = document.getElementById('root')
if (!rootEl) throw new Error('루트 DOM 요소(#root)를 찾을 수 없습니다.')

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
