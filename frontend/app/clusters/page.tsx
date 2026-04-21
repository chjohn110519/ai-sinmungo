'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Users, TrendingUp, CheckCircle, ArrowLeft } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

interface ClusterSummary {
  cluster_id: string
  topic: string
  keywords: string[]
  responsible_dept: string
  classification: string
  count: number
  threshold: number
  triggered: boolean
  progress_percent: number
}

export default function ClustersPage() {
  const [clusters, setClusters] = useState<ClusterSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'전체' | '제안' | '청원'>('전체')

  useEffect(() => {
    const load = () => {
      const params = filter !== '전체' ? `?classification=${filter}` : ''
      fetch(`${API_BASE}/api/clusters${params}`)
        .then(r => r.json())
        .then(data => setClusters(data.clusters || []))
        .catch(() => setClusters([]))
        .finally(() => setLoading(false))
    }
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [filter])

  return (
    <main className="min-h-screen bg-gradient-to-b from-white via-blue-50 to-gray-50">
      <nav className="sticky top-0 z-40 border-b border-gray-200 bg-white/80 backdrop-blur-sm">
        <div className="mx-auto max-w-4xl px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900">
              <ArrowLeft size={16} />
              홈으로
            </Link>
            <span className="text-gray-300">/</span>
            <span className="text-sm font-bold text-gray-900">집계 현황</span>
          </div>
          <Link href="/#chat" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors">
            의견 제출하기
          </Link>
        </div>
      </nav>

      <div className="mx-auto max-w-4xl px-4 py-8 space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">시민 제안 집계 현황</h1>
          <p className="text-gray-600">같은 방향의 제안이 모여 공식 문서가 되는 과정을 확인하세요.</p>
        </div>

        {/* 필터 */}
        <div className="flex gap-2">
          {(['전체', '제안', '청원'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                filter === f ? 'bg-blue-600 text-white' : 'bg-white border border-gray-200 text-gray-700 hover:border-blue-300'
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        {/* 목록 */}
        {loading ? (
          <div className="text-center py-16 text-gray-400 text-sm">불러오는 중...</div>
        ) : clusters.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-gray-400 text-sm mb-4">아직 집계된 제안이 없습니다.</p>
            <Link href="/#chat" className="text-blue-600 text-sm hover:underline">첫 번째 의견을 제출해보세요 →</Link>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {clusters.map(c => (
              <Link key={c.cluster_id} href={`/cluster/${c.cluster_id}`} className="block group">
                <div className={`rounded-2xl border p-5 shadow-sm transition-all group-hover:shadow-md group-hover:border-blue-300 ${
                  c.triggered ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-white'
                }`}>
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="flex items-center gap-2">
                      {c.triggered
                        ? <CheckCircle size={16} className="text-green-600 flex-shrink-0" />
                        : <TrendingUp size={16} className="text-blue-600 flex-shrink-0" />
                      }
                      <span className="font-semibold text-gray-900 text-sm">{c.topic}</span>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      c.classification === '제안' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'
                    }`}>
                      {c.classification}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 mb-3">
                    <Users size={13} className="text-gray-400" />
                    <span className="text-2xl font-bold text-gray-900">{c.count.toLocaleString()}</span>
                    <span className="text-gray-500 text-sm">명 참여</span>
                    <span className="text-gray-300 mx-1">·</span>
                    <span className="text-xs text-gray-500">{c.responsible_dept}</span>
                  </div>

                  {!c.triggered && (
                    <div className="space-y-1 mb-3">
                      <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-blue-400 to-blue-600 rounded-full"
                          style={{ width: `${Math.min(c.progress_percent, 100)}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-400">{c.progress_percent}% 달성 (목표 {c.threshold.toLocaleString()}명)</p>
                    </div>
                  )}

                  {c.triggered && (
                    <p className="text-xs text-green-700 font-medium mb-3">✓ 공식 제안서 생성 완료</p>
                  )}

                  {c.keywords.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {c.keywords.slice(0, 4).map(kw => (
                        <span key={kw} className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">
                          {kw}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
