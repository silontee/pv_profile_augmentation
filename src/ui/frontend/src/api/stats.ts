// ============================================================
// 통계 API 클라이언트
// ============================================================

import type { Stats } from '../types'

/**
 * 대시보드 요약 통계 조회 (백엔드 캐시 TTL 60s)
 * GET /api/stats
 */
export async function fetchStats(): Promise<Stats> {
  const res = await fetch('/api/stats')
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
    throw Object.assign(new Error(err.error ?? '통계 조회 실패'), { status: res.status })
  }
  return res.json() as Promise<Stats>
}
