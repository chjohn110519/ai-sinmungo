'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, FileText, CheckCircle, Clock, TrendingUp, Scale } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

interface ProposalData {
  proposal_id: string
  title: string
  background: string
  core_requests: string
  expected_effects: string
  responsible_dept: string
  related_laws: string[]
  created_at: string | null
  analysis: {
    pass_probability: number | null
    expected_duration_days: number | null
    feasibility_score: number | null
  } | null
}

export default function ResultPage() {
  const params = useParams()
  const proposalId = params?.proposal_id as string

  const [proposal, setProposal] = useState<ProposalData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!proposalId) return
    fetch(`${API_BASE}/api/proposal/${proposalId}`)
      .then(r => {
        if (!r.ok) throw new Error('제안서를 불러올 수 없습니다.')
        return r.json()
      })
      .then(setProposal)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [proposalId])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-gray-500 text-sm">불러오는 중...</div>
      </div>
    )
  }

  if (error || !proposal) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 gap-4">
        <p className="text-red-500 text-sm">{error || '제안서를 찾을 수 없습니다.'}</p>
        <Link href="/clusters" className="text-blue-600 text-sm hover:underline">← 집계 현황으로</Link>
      </div>
    )
  }

  const passPct = proposal.analysis?.pass_probability != null
    ? Math.round(proposal.analysis.pass_probability * 100)
    : null
  const durationDays = proposal.analysis?.expected_duration_days ?? null
  const feasibility = proposal.analysis?.feasibility_score != null
    ? Math.round(proposal.analysis.feasibility_score * 100)
    : null

  return (
    <main className="min-h-screen bg-gradient-to-b from-white via-blue-50 to-gray-50">
      <nav className="sticky top-0 z-40 border-b border-gray-200 bg-white/80 backdrop-blur-sm">
        <div className="mx-auto max-w-3xl px-4 py-4 flex items-center gap-3">
          <Link href="/clusters" className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900">
            <ArrowLeft size={16} />
            집계 현황
          </Link>
          <span className="text-gray-300">/</span>
          <span className="text-sm font-medium text-gray-800">공식 제안서</span>
        </div>
      </nav>

      <div className="mx-auto max-w-3xl px-4 py-8 space-y-6">
        {/* 헤더 */}
        <div className="rounded-2xl bg-gradient-to-br from-green-500 to-green-600 p-6 text-white shadow-lg">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle size={20} className="text-white" />
            <span className="text-sm font-medium text-green-100">AI 자동 생성 공식 제안서</span>
          </div>
          <h1 className="text-2xl font-bold leading-tight mb-2">{proposal.title}</h1>
          <div className="flex items-center gap-2 text-green-100 text-sm">
            <span>{proposal.responsible_dept}</span>
            {proposal.created_at && (
              <>
                <span className="text-green-300">·</span>
                <span>{new Date(proposal.created_at).toLocaleDateString('ko-KR')}</span>
              </>
            )}
          </div>
        </div>

        {/* 분석 수치 */}
        {proposal.analysis && (
          <div className="grid grid-cols-3 gap-4">
            {passPct !== null && (
              <div className="bg-white rounded-2xl border border-gray-200 p-4 text-center shadow-sm">
                <TrendingUp size={20} className="text-blue-600 mx-auto mb-2" />
                <div className="text-2xl font-bold text-gray-900">{passPct}%</div>
                <div className="text-xs text-gray-500 mt-1">통과 예측</div>
              </div>
            )}
            {durationDays !== null && (
              <div className="bg-white rounded-2xl border border-gray-200 p-4 text-center shadow-sm">
                <Clock size={20} className="text-amber-500 mx-auto mb-2" />
                <div className="text-2xl font-bold text-gray-900">{durationDays}</div>
                <div className="text-xs text-gray-500 mt-1">예상 소요일</div>
              </div>
            )}
            {feasibility !== null && (
              <div className="bg-white rounded-2xl border border-gray-200 p-4 text-center shadow-sm">
                <CheckCircle size={20} className="text-green-600 mx-auto mb-2" />
                <div className="text-2xl font-bold text-gray-900">{feasibility}%</div>
                <div className="text-xs text-gray-500 mt-1">타당성 점수</div>
              </div>
            )}
          </div>
        )}

        {/* 제안 배경 */}
        {proposal.background && (
          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm space-y-2">
            <h2 className="font-bold text-gray-900 flex items-center gap-2">
              <FileText size={16} className="text-blue-600" />
              제안 배경
            </h2>
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">{proposal.background}</p>
          </div>
        )}

        {/* 핵심 요청사항 */}
        {proposal.core_requests && (
          <div className="bg-blue-50 rounded-2xl border border-blue-200 p-6 shadow-sm space-y-2">
            <h2 className="font-bold text-blue-900 flex items-center gap-2">
              <CheckCircle size={16} className="text-blue-600" />
              핵심 요청사항
            </h2>
            <p className="text-sm text-blue-800 leading-relaxed whitespace-pre-line">{proposal.core_requests}</p>
          </div>
        )}

        {/* 기대 효과 */}
        {proposal.expected_effects && (
          <div className="bg-green-50 rounded-2xl border border-green-200 p-6 shadow-sm space-y-2">
            <h2 className="font-bold text-green-900 flex items-center gap-2">
              <TrendingUp size={16} className="text-green-600" />
              기대 효과
            </h2>
            <p className="text-sm text-green-800 leading-relaxed whitespace-pre-line">{proposal.expected_effects}</p>
          </div>
        )}

        {/* 관련 법령 */}
        {proposal.related_laws.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm space-y-3">
            <h2 className="font-bold text-gray-900 flex items-center gap-2">
              <Scale size={16} className="text-purple-600" />
              관련 법령
            </h2>
            <div className="flex flex-wrap gap-2">
              {proposal.related_laws.map(law => (
                <span key={law} className="px-3 py-1 bg-purple-50 border border-purple-200 text-purple-700 text-sm rounded-full">
                  {law}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* 하단 CTA */}
        <div className="text-center space-y-3 pt-2">
          <Link
            href="/clusters"
            className="inline-block px-6 py-2.5 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 transition-colors text-sm"
          >
            집계 현황으로 돌아가기
          </Link>
          <div>
            <Link href="/#chat" className="text-sm text-gray-500 hover:text-gray-700">
              같은 의견 제출하기 →
            </Link>
          </div>
        </div>
      </div>
    </main>
  )
}
