// ============================================================
// DB 장애 에러 배너 컴포넌트
// 503 응답 수신 시 화면 상단에 표시
// ============================================================

import React from 'react'
import { useUiStore } from '../../stores/uiStore'

export const ErrorBanner: React.FC = () => {
  const dbError    = useUiStore((s) => s.dbError)
  const setDbError = useUiStore((s) => s.setDbError)

  if (!dbError) return null

  return (
    <div
      role="alert"
      className="flex items-center justify-between px-4 py-2.5 bg-red-900/80 border-b border-red-700 text-sm text-red-100 z-50"
    >
      <div className="flex items-center gap-2">
        {/* 경고 아이콘 */}
        <svg
          className="w-4 h-4 flex-shrink-0 text-red-300"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
          />
        </svg>
        <span>
          데이터를 불러올 수 없습니다.{' '}
          <strong>잠시 후 다시 시도해주세요.</strong>
          {' '}(서버 점검 중)
        </span>
      </div>
      {/* 닫기 버튼 */}
      <button
        onClick={() => setDbError(false)}
        className="ml-4 p-1 rounded hover:bg-red-700/50 transition-colors"
        aria-label="오류 배너 닫기"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}
