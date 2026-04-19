'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { Search, Filter, RefreshCw, ExternalLink, Clock, CheckCircle, AlertCircle, ChevronLeft, ChevronRight } from 'lucide-react'

interface ComplaintItem {
  session_id: string
  created_at: string | null
  status: string
  classification: string | null
  proposal_title: string | null
}

interface ComplaintsResponse {
  total: number
  page: number
  page_size: number
  total_pages: number
  items: ComplaintItem[]
}

const STATUS_KO: Record<string, string> = {
  in_progress: '처리 중', classified: '분류 완료', structured: '구조화 완료',
  completed: '완료', failed: '실패',
}
const STATUS_COLOR: Record<string, string> = {
  completed: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  failed: 'bg-red-100 text-red-700 border-red-200',
  in_progress: 'bg-blue-100 text-blue-700 border-blue-200',
  classified: 'bg-sky-100 text-sky-700 border-sky-200',
  structured: 'bg-indigo-100 text-indigo-700 border-indigo-200',
}
const CLASS_COLOR: Record<string, string> = {
  민원: 'bg-orange-100 text-orange-700',
  제안: 'bg-blue-100 text-blue-700',
  청원: 'bg-purple-100 text-purple-700',
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'completed') return <CheckCircle className="h-4 w-4 text-emerald-500" />
  if (status === 'failed') return <AlertCircle className="h-4 w-4 text-red-500" />
  return <Clock className="h-4 w-4 text-blue-500 animate-pulse" />
}

export default function ComplaintsPage() {
  const [data, setData] = useState<ComplaintsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [classFilter, setClassFilter] = useState('')
  const [myOnly, setMyOnly] = useState(false)
  const [myIds, setMyIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem('complaint_sessions') || '[]')
      setMyIds(new Set(stored))
    } catch {}
  }, [])

  const fetchData = useCallback(() => {
    setLoading(true)
    const params = new URLSearchParams({ page: String(page), page_size: '15' })
    if (statusFilter) params.set('status', statusFilter)
    if (classFilter) params.set('classification', classFilter)
    fetch(`/api/sessions?${params}`)
      .then((r) => r.json())
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [page, statusFilter, classFilter])

  useEffect(() => { fetchData() }, [fetchData])

  const displayItems = myOnly
    ? (data?.items ?? []).filter((i) => myIds.has(i.session_id))
    : (data?.items ?? [])

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 헤더 */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-sm text-gray-500 hover:text-blue-600">← 홈</Link>
            <h1 className="text-xl font-bold text-gray-900">민원 목록</h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMyOnly((v) => !v)}
              className={`px-3 py-1.5 text-sm rounded-lg border transition ${
                myOnly ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
              }`}
            >
              내 접수만
            </button>
            <button onClick={fetchData} className="p-1.5 text-gray-500 hover:text-blue-600 transition">
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
        {/* 필터 바 */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-4 flex flex-wrap gap-3 items-center">
          <Filter className="h-4 w-4 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
            className="text-sm rounded-lg border border-gray-300 px-3 py-1.5 text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          >
            <option value="">전체 상태</option>
            <option value="in_progress">처리 중</option>
            <option value="completed">완료</option>
            <option value="failed">실패</option>
          </select>
          <select
            value={classFilter}
            onChange={(e) => { setClassFilter(e.target.value); setPage(1) }}
            className="text-sm rounded-lg border border-gray-300 px-3 py-1.5 text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          >
            <option value="">전체 유형</option>
            <option value="민원">민원</option>
            <option value="제안">제안</option>
            <option value="청원">청원</option>
          </select>
          {(statusFilter || classFilter) && (
            <button
              onClick={() => { setStatusFilter(''); setClassFilter(''); setPage(1) }}
              className="text-sm text-red-500 hover:underline"
            >
              필터 초기화
            </button>
          )}
          {data && (
            <span className="ml-auto text-sm text-gray-500">
              총 <strong>{data.total}</strong>건
            </span>
          )}
        </div>

        {/* 목록 */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : displayItems.length === 0 ? (
            <div className="py-20 text-center text-gray-400">
              <Search className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm">{myOnly ? '내가 접수한 민원이 없습니다.' : '접수된 민원이 없습니다.'}</p>
              <Link href="/" className="mt-4 inline-block text-sm text-blue-600 hover:underline">민원 접수하기 →</Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-100">
                  <tr className="text-left text-xs text-gray-500 uppercase tracking-wider">
                    <th className="px-5 py-3">접수번호</th>
                    <th className="px-5 py-3">접수 시각</th>
                    <th className="px-5 py-3">유형</th>
                    <th className="px-5 py-3">상태</th>
                    <th className="px-5 py-3">제안서 제목</th>
                    <th className="px-5 py-3">바로가기</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {displayItems.map((item) => (
                    <tr
                      key={item.session_id}
                      className={`hover:bg-blue-50/40 transition ${myIds.has(item.session_id) ? 'bg-blue-50/20' : ''}`}
                    >
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-2">
                          {myIds.has(item.session_id) && (
                            <span className="text-[10px] bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded-full font-semibold">나</span>
                          )}
                          <span className="font-mono text-xs text-gray-500">{item.session_id.slice(0, 8)}…</span>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-gray-600">
                        {item.created_at
                          ? new Date(item.created_at).toLocaleString('ko-KR', {
                              month: '2-digit', day: '2-digit',
                              hour: '2-digit', minute: '2-digit',
                            })
                          : '-'}
                      </td>
                      <td className="px-5 py-4">
                        {item.classification ? (
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${CLASS_COLOR[item.classification] || 'bg-gray-100 text-gray-600'}`}>
                            {item.classification}
                          </span>
                        ) : <span className="text-gray-400">-</span>}
                      </td>
                      <td className="px-5 py-4">
                        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold border ${STATUS_COLOR[item.status] || 'bg-gray-100 text-gray-600 border-gray-200'}`}>
                          <StatusIcon status={item.status} />
                          {STATUS_KO[item.status] || item.status}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-gray-700 max-w-[220px] truncate">
                        {item.proposal_title || <span className="text-gray-400">-</span>}
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-2">
                          <Link href={`/status/${item.session_id}`} className="text-xs text-gray-500 hover:text-blue-600 hover:underline">
                            현황
                          </Link>
                          {item.status === 'completed' && (
                            <Link href={`/result/${item.session_id}`} className="text-xs text-blue-600 hover:underline flex items-center gap-0.5">
                              결과 <ExternalLink className="h-3 w-3" />
                            </Link>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* 페이지네이션 */}
        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-2 rounded-lg border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            {Array.from({ length: Math.min(5, data.total_pages) }, (_, i) => {
              const p = Math.max(1, Math.min(page - 2, data.total_pages - 4)) + i
              return (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`w-9 h-9 rounded-lg text-sm font-semibold transition ${
                    p === page
                      ? 'bg-blue-600 text-white'
                      : 'border border-gray-300 bg-white text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {p}
                </button>
              )
            })}
            <button
              onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
              disabled={page === data.total_pages}
              className="p-2 rounded-lg border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        )}
      </main>
    </div>
  )
}
