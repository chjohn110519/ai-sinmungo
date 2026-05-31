'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Users, TrendingUp, CheckCircle, ArrowLeft, FileText, Clock, ChevronDown, ChevronUp, MessageSquare } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

interface ClusterData {
  cluster_id: string
  topic: string
  keywords: string[]
  responsible_dept: string
  classification: string
  count: number
  threshold: number
  triggered: boolean
  proposal_id: string | null
  progress_percent: number
  created_at: string | null
  updated_at: string | null
}

interface Opinion {
  session_id: string
  created_at: string | null
  message: string
  classification: string | null
  proposal_title: string | null
}

const CLASS_COLOR: Record<string, string> = {
  민원: 'bg-orange-100 text-orange-700',
  제안: 'bg-blue-100 text-blue-700',
  청원: 'bg-purple-100 text-purple-700',
}

function OpinionCard({ op }: { op: Opinion }) {
  const [expanded, setExpanded] = useState(false)
  const isLong = op.message.length > 100
  const preview = isLong && !expanded ? op.message.slice(0, 100) + '…' : op.message

  return (
    <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-gray-400">#{op.session_id}</span>
          {op.classification && (
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${CLASS_COLOR[op.classification] ?? 'bg-gray-100 text-gray-600'}`}>
              {op.classification}
            </span>
          )}
        </div>
        {op.created_at && (
          <span className="text-xs text-gray-400 flex-shrink-0">
            {new Date(op.created_at).toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </div>
      {op.message ? (
        <div>
          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{preview}</p>
          {isLong && (
            <button
              onClick={() => setExpanded(v => !v)}
              className="mt-1 flex items-center gap-1 text-xs text-blue-600 hover:underline"
            >
              {expanded ? <><ChevronUp size={12} /> 접기</> : <><ChevronDown size={12} /> 더 보기</>}
            </button>
          )}
        </div>
      ) : (
        <p className="text-xs text-gray-400 italic">내용 없음</p>
      )}
      {op.proposal_title && (
        <p className="text-xs text-gray-500">📄 제안서: {op.proposal_title}</p>
      )}
    </div>
  )
}

export default function ClusterPage() {
  const params = useParams()
  const clusterId = params?.cluster_id as string
  const router = useRouter()

  const [cluster, setCluster] = useState<ClusterData | null>(null)
  const [opinions, setOpinions] = useState<Opinion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!clusterId) return

    Promise.all([
      fetch(`${API_BASE}/api/cluster/${clusterId}`)
        .then(r => { if (!r.ok) throw new Error('클러스터 정보를 불러올 수 없습니다.'); return r.json() }),
      fetch(`${API_BASE}/api/cluster/${clusterId}/opinions`)
        .then(r => r.ok ? r.json() : { opinions: [] })
        .catch(() => ({ opinions: [] })),
    ])
      .then(([clusterData, opData]) => {
        setCluster(clusterData)
        setOpinions(opData.opinions || [])
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [clusterId])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-gray-500 text-sm">불러오는 중...</div>
      </div>
    )
  }

  if (error || !cluster) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 gap-4">
        <p className="text-red-500 text-sm">{error || '클러스터를 찾을 수 없습니다.'}</p>
        <Link href="/" className="text-blue-600 text-sm hover:underline">← 홈으로</Link>
      </div>
    )
  }

  const remaining = Math.max(0, cluster.threshold - cluster.count)

  return (
    <main className="min-h-screen bg-gradient-to-b from-white via-blue-50 to-gray-50">
      {/* 네비게이션 */}
      <nav className="sticky top-0 z-40 border-b border-gray-200 bg-white/80 backdrop-blur-sm">
        <div className="mx-auto max-w-3xl px-4 py-4 flex items-center gap-3">
          <Link href="/" className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900">
            <ArrowLeft size={16} />
            홈으로
          </Link>
          <span className="text-gray-300">/</span>
          <span className="text-sm font-medium text-gray-800">집계 현황</span>
        </div>
      </nav>

      <div className="mx-auto max-w-3xl px-4 py-8 space-y-6">
        {/* 헤더 카드 */}
        <div className={`rounded-2xl p-6 text-white shadow-lg ${
          cluster.triggered
            ? 'bg-gradient-to-br from-green-500 to-green-600'
            : 'bg-gradient-to-br from-blue-600 to-blue-700'
        }`}>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs px-2 py-0.5 rounded-full bg-white/20 font-medium">
              {cluster.classification}
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-white/20 font-medium">
              {cluster.topic}
            </span>
          </div>
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-blue-100 text-sm mb-1">{cluster.responsible_dept}</p>
              <div className="flex items-baseline gap-2">
                <span className="text-5xl font-bold">{cluster.count.toLocaleString()}</span>
                <span className="text-blue-100">명 참여</span>
              </div>
            </div>
            {cluster.triggered ? (
              <div className="flex flex-col items-center gap-1">
                <CheckCircle size={40} className="text-white" />
                <span className="text-xs text-white/80">문서 생성 완료</span>
              </div>
            ) : (
              <div className="text-right">
                <div className="text-3xl font-bold">{cluster.progress_percent}%</div>
                <div className="text-blue-100 text-xs">목표 달성률</div>
              </div>
            )}
          </div>
        </div>

        {/* 진행 상황 */}
        {!cluster.triggered && (
          <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-4 shadow-sm">
            <h2 className="font-bold text-gray-900">공식 문서 생성까지</h2>
            <div className="space-y-2">
              <div className="flex justify-between text-sm text-gray-600">
                <span>{cluster.count.toLocaleString()}명 참여</span>
                <span>목표 {cluster.threshold.toLocaleString()}명</span>
              </div>
              <div className="w-full h-3 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-400 to-blue-600 rounded-full transition-all"
                  style={{ width: `${Math.min(cluster.progress_percent, 100)}%` }}
                />
              </div>
            </div>
            {remaining > 0 ? (
              <p className="text-sm text-gray-600">
                <span className="font-semibold text-blue-600">{remaining.toLocaleString()}명</span>이 더 같은 의견을 제출하면
                AI가 이 주제를 공식 제안서로 자동 생성합니다.
              </p>
            ) : (
              <p className="text-sm text-green-700 font-medium">목표 달성! 곧 공식 제안서가 생성됩니다.</p>
            )}
          </div>
        )}

        {/* 생성된 제안서 링크 */}
        {cluster.triggered && cluster.proposal_id && (
          <div className="bg-green-50 rounded-2xl border border-green-200 p-5 flex items-center gap-4">
            <FileText size={32} className="text-green-600 flex-shrink-0" />
            <div className="flex-1">
              <p className="font-bold text-green-800">공식 제안서가 생성되었습니다</p>
              <p className="text-sm text-green-700">{cluster.count.toLocaleString()}명의 목소리가 하나의 제안서로 구조화되었습니다.</p>
            </div>
            <Link
              href={`/proposal/${cluster.proposal_id}`}
              className="flex-shrink-0 px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-semibold hover:bg-green-700 transition-colors"
            >
              제안서 보기
            </Link>
          </div>
        )}

        {/* 키워드 */}
        <div className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm space-y-3">
          <div className="flex items-center gap-2">
            <TrendingUp size={16} className="text-blue-600" />
            <h3 className="font-bold text-gray-900">관련 키워드</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {cluster.keywords.map(kw => (
              <span key={kw} className="px-3 py-1 bg-blue-50 border border-blue-200 text-blue-700 text-sm rounded-full">
                {kw}
              </span>
            ))}
          </div>
        </div>

        {/* 제출된 의견 목록 */}
        <div className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MessageSquare size={16} className="text-blue-600" />
              <h3 className="font-bold text-gray-900">제출된 의견</h3>
            </div>
            <span className="text-xs text-gray-500">{opinions.length}건</span>
          </div>

          {opinions.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-4">아직 개별 의견 데이터가 없습니다.</p>
          ) : (
            <div className="space-y-3">
              {opinions.map((op, i) => (
                <OpinionCard key={i} op={op} />
              ))}
            </div>
          )}
        </div>

        {/* 참여 안내 */}
        <div className="bg-blue-600 rounded-2xl p-6 text-white text-center space-y-3">
          <div className="flex items-center justify-center gap-2">
            <Users size={20} />
            <h3 className="font-bold">같은 의견이 있으신가요?</h3>
          </div>
          <p className="text-blue-100 text-sm">
            아래에서 의견을 제출하면 이 집계에 자동으로 반영됩니다.
          </p>
          <button
            onClick={() => router.push(`/?cluster=${clusterId}`)}
            className="inline-block px-6 py-2.5 bg-white text-blue-600 rounded-xl font-semibold hover:bg-blue-50 transition-colors text-sm cursor-pointer"
          >
            의견 제출하기
          </button>
        </div>

        {/* 메타 정보 */}
        <div className="text-xs text-gray-400 flex items-center gap-1.5 justify-center">
          <Clock size={12} />
          {cluster.created_at && (
            <span>최초 제안: {new Date(cluster.created_at).toLocaleDateString('ko-KR')}</span>
          )}
          {cluster.updated_at && (
            <span> · 마지막 업데이트: {new Date(cluster.updated_at).toLocaleDateString('ko-KR')}</span>
          )}
        </div>
      </div>
    </main>
  )
}
