'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

interface AdminStats {
  total_sessions: number
  classification_breakdown: { 민원: number; 제안: number; 청원: number }
  status_breakdown: Record<string, number>
  avg_feasibility_score: number
  avg_pass_probability: number
  recent_sessions: Array<{
    session_id: string
    created_at: string
    status: string
    classification: string | null
    proposal_title: string | null
  }>
}

const CLASS_COLORS = { 민원: '#f97316', 제안: '#3b82f6', 청원: '#8b5cf6' }
const STATUS_KO: Record<string, string> = {
  in_progress: '처리 중', classified: '분류 완료', structured: '구조화 완료',
  completed: '완료', failed: '실패',
}
const STATUS_COLOR: Record<string, string> = {
  completed: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-red-100 text-red-700',
  in_progress: 'bg-blue-100 text-blue-700',
  classified: 'bg-sky-100 text-sky-700',
  structured: 'bg-indigo-100 text-indigo-700',
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white rounded-2xl shadow-md p-5">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-3xl font-bold text-gray-900">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  )
}

export default function AdminPage() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState(new Date())

  const fetchStats = () => {
    setLoading(true)
    fetch(`${API_BASE}/api/admin/stats`)
      .then((r) => {
        if (!r.ok) throw new Error('통계를 불러올 수 없습니다.')
        return r.json()
      })
      .then((d) => { setStats(d); setLastRefresh(new Date()) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchStats() }, [])

  if (loading && !stats) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center text-red-500">{error}</div>
    )
  }

  const classPieData = stats
    ? Object.entries(stats.classification_breakdown).map(([name, value]) => ({ name, value }))
    : []

  const statusBarData = stats
    ? Object.entries(stats.status_breakdown).map(([name, value]) => ({
        name: STATUS_KO[name] || name, value,
      }))
    : []

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-sm text-gray-500 hover:text-blue-600">← 홈</Link>
          <h1 className="text-xl font-bold text-gray-900">관리자 대시보드</h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400">
            최종 갱신: {lastRefresh.toLocaleTimeString('ko-KR')}
          </span>
          <button
            onClick={fetchStats}
            className="px-3 py-1.5 text-sm rounded-lg bg-blue-50 text-blue-600 hover:bg-blue-100 transition"
          >
            새로고침
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8 space-y-8">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard label="총 접수" value={stats?.total_sessions ?? 0} sub="누적 세션" />
          <StatCard
            label="평균 실현 가능성"
            value={`${((stats?.avg_feasibility_score ?? 0) * 100).toFixed(1)}%`}
          />
          <StatCard
            label="평균 통과 확률"
            value={`${((stats?.avg_pass_probability ?? 0) * 100).toFixed(1)}%`}
          />
          <StatCard
            label="완료율"
            value={
              stats && stats.total_sessions > 0
                ? `${(((stats.status_breakdown['completed'] ?? 0) / stats.total_sessions) * 100).toFixed(0)}%`
                : '0%'
            }
            sub={`완료 ${stats?.status_breakdown['completed'] ?? 0}건`}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl shadow-md p-6">
            <h2 className="font-semibold text-gray-800 mb-4">유형별 분류 현황</h2>
            {classPieData.some((d) => d.value > 0) ? (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={classPieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name} ${value}`}>
                    {classPieData.map((entry) => (
                      <Cell key={entry.name} fill={CLASS_COLORS[entry.name as keyof typeof CLASS_COLORS] || '#94a3b8'} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[220px] flex items-center justify-center text-gray-400 text-sm">데이터 없음</div>
            )}
          </div>

          <div className="bg-white rounded-2xl shadow-md p-6">
            <h2 className="font-semibold text-gray-800 mb-4">처리 상태별 현황</h2>
            {statusBarData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={statusBarData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[220px] flex items-center justify-center text-gray-400 text-sm">데이터 없음</div>
            )}
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-md p-6">
          <h2 className="font-semibold text-gray-800 mb-4">최근 접수 목록</h2>
          {stats && stats.recent_sessions.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 text-left text-xs text-gray-500 uppercase tracking-wider">
                    <th className="pb-3 pr-4">세션 ID</th>
                    <th className="pb-3 pr-4">접수 시각</th>
                    <th className="pb-3 pr-4">유형</th>
                    <th className="pb-3 pr-4">상태</th>
                    <th className="pb-3 pr-4">제안서 제목</th>
                    <th className="pb-3">링크</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {stats.recent_sessions.map((s) => (
                    <tr key={s.session_id} className="hover:bg-gray-50 transition">
                      <td className="py-3 pr-4 font-mono text-xs text-gray-500">
                        {s.session_id.slice(0, 8)}…
                      </td>
                      <td className="py-3 pr-4 text-gray-700">
                        {s.created_at
                          ? new Date(s.created_at).toLocaleString('ko-KR', {
                              month: '2-digit', day: '2-digit',
                              hour: '2-digit', minute: '2-digit',
                            })
                          : '-'}
                      </td>
                      <td className="py-3 pr-4">
                        {s.classification ? (
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                            s.classification === '민원' ? 'bg-orange-100 text-orange-700'
                            : s.classification === '제안' ? 'bg-blue-100 text-blue-700'
                            : 'bg-purple-100 text-purple-700'
                          }`}>
                            {s.classification}
                          </span>
                        ) : <span className="text-gray-400">-</span>}
                      </td>
                      <td className="py-3 pr-4">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${STATUS_COLOR[s.status] || 'bg-gray-100 text-gray-600'}`}>
                          {STATUS_KO[s.status] || s.status}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-gray-700 max-w-[200px] truncate">
                        {s.proposal_title || <span className="text-gray-400">-</span>}
                      </td>
                      <td className="py-3 space-x-2">
                        <Link href={`/result/${s.session_id}`} className="text-xs text-blue-600 hover:underline">결과</Link>
                        <Link href={`/status/${s.session_id}`} className="text-xs text-gray-500 hover:underline">현황</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center text-gray-400 py-8">아직 접수된 민원이 없습니다.</div>
          )}
        </div>
      </main>
    </div>
  )
}
