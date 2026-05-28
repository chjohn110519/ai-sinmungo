'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, RadialBarChart, RadialBar, Legend,
} from 'recharts'
import { FileText, Download, Loader2 } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

interface SessionResult {
  session: { session_id: string; status: string; final_classification: string }
  proposal: {
    title: string; background: string; core_requests: string
    expected_effects: string; responsible_dept: string; related_laws: string[]
  } | null
  analysis: {
    similar_cases: Array<{ case_id: string; similarity: number; title: string }>
    pass_probability: number; expected_duration_days: number
    feasibility_score: number
    visualization_data: {
      timeline: Array<{ name: string; value: number }>
      committee_recommendations?: Array<{ committee: string; relevance: number }>
      stage_predictions?: {
        predicted_progress_stage: string
        predicted_proc_result: string
        predicted_cmt_result: string
        predicted_law_result: string
        top_progress_stages: Array<{ label: string; probability: number }>
      } | null
    }
  } | null
  draft_analysis?: {
    pass_probability: number
    expected_duration_days: number
  } | null
  review?: { validity_score: number; strengths: string[]; weaknesses: string[] } | null
  download_url?: string | null
}

interface BillArticle { article_number: number; title: string; content: string }
interface FormalBill {
  bill_number: string; bill_title: string; purpose: string; main_content: string
  articles: BillArticle[]; supplementary_provisions: string
  proposer: string; expected_committee: string; related_laws: string[]
}

const CLASS_COLOR: Record<string, string> = {
  민원: 'bg-orange-100 text-orange-700',
  제안: 'bg-blue-100 text-blue-700',
  청원: 'bg-purple-100 text-purple-700',
}

export default function ResultPage() {
  const params = useParams()
  const router = useRouter()
  const sessionId = params['session_id'] as string

  const [result, setResult] = useState<SessionResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 법안 생성 상태
  const [bill, setBill] = useState<FormalBill | null>(null)
  const [billLoading, setBillLoading] = useState(false)
  const [billError, setBillError] = useState<string | null>(null)
  const [showBill, setShowBill] = useState(false)

  useEffect(() => {
    if (!sessionId) return

    // 1순위: window.__pendingResult (same-tab navigation, 가장 신뢰성 높음)
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const pending = (window as any).__pendingResult
      if (pending && pending.sid === sessionId) {
        setResult(pending.data)
        setLoading(false)
        return
      }
    } catch {}

    // 2순위: sessionStorage (same-tab, 동기 보장)
    try {
      const raw = sessionStorage.getItem('__pending_result')
      if (raw) {
        const { sid, data } = JSON.parse(raw)
        if (sid === sessionId) {
          setResult(data)
          setLoading(false)
          return
        }
      }
    } catch {}

    // 3순위: localStorage (이전 방문 데이터)
    try {
      const stored = localStorage.getItem(`result_${sessionId}`)
      if (stored) {
        setResult(JSON.parse(stored))
        setLoading(false)
        return
      }
    } catch {}

    // 4순위: API (DB가 ephemeral이라 실패할 수 있음)
    fetch(`${API_BASE}/api/session/${sessionId}/result`)
      .then((r) => { if (!r.ok) throw new Error('not_found'); return r.json() })
      .then(setResult)
      .catch(() => setError('no_data'))
      .finally(() => setLoading(false))
  }, [sessionId])

  const handleGenerateBill = async () => {
    setBillLoading(true)
    setBillError(null)
    try {
      const r = await fetch(`${API_BASE}/api/session/${sessionId}/bill`, { method: 'POST' })
      if (!r.ok) {
        const err = await r.json()
        throw new Error(err.detail || '법안 생성 실패')
      }
      const data = await r.json()
      setBill(data)
      setShowBill(true)
    } catch (e: unknown) {
      setBillError(e instanceof Error ? e.message : '법안 생성 중 오류')
    } finally {
      setBillLoading(false)
    }
  }

  const downloadBill = () => {
    if (!bill) return
    const text = formatBillText(bill)
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${bill.bill_title}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )

  if (error || !result) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center space-y-3 max-w-sm">
        <p className="text-red-500 font-semibold text-lg">결과를 불러올 수 없습니다</p>
        <p className="text-sm text-gray-500 leading-relaxed">
          민원 작성을 완료한 후 결과 화면에서<br />
          <strong>&#39;상세 결과 보기&#39;</strong> 버튼을 눌러 이동해주세요.<br />
          URL을 직접 입력하면 데이터가 없을 수 있습니다.
        </p>
        <button
          onClick={() => router.push('/')}
          className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 transition"
        >
          홈으로 돌아가기
        </button>
      </div>
    </div>
  )

  const { session, proposal, analysis, review, download_url } = result
  const canGenerateBill = ['제안', '청원'].includes(session.final_classification)

  // 타당성 점수(feasibility_score) 제거 — 통과 확률만 표시
  const radialData = analysis ? [
    { name: '통과 확률', value: Math.round(analysis.pass_probability * 100), fill: '#10b981' },
  ] : []
  const stagePredictions = analysis?.visualization_data?.stage_predictions ?? null

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* 헤더 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => router.push('/')} className="text-sm text-gray-500 hover:text-blue-600">← 홈</button>
            <Link href={`/status/${sessionId}`} className="text-sm text-gray-500 hover:text-blue-600">처리 현황</Link>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm font-semibold ${CLASS_COLOR[session.final_classification] || 'bg-gray-100 text-gray-700'}`}>
            {session.final_classification}
          </span>
        </div>

        {/* 제안서 카드 */}
        {proposal ? (
          <div className="bg-white rounded-2xl shadow-md p-6 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <h1 className="text-2xl font-bold text-gray-900">{proposal.title}</h1>
              {/* 법안 생성 버튼 (제안/청원만) */}
              {canGenerateBill && (
                <button
                  onClick={handleGenerateBill}
                  disabled={billLoading}
                  className="flex-shrink-0 inline-flex items-center gap-2 rounded-full bg-purple-600 hover:bg-purple-700 disabled:opacity-50 px-4 py-2 text-sm font-semibold text-white transition shadow-md"
                >
                  {billLoading ? <Loader2 size={15} className="animate-spin" /> : <FileText size={15} />}
                  {billLoading ? '생성 중…' : '법안 생성'}
                </button>
              )}
            </div>
            <p className="text-sm text-gray-500">담당 부처: {proposal.responsible_dept}</p>

            {billError && (
              <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-600">{billError}</div>
            )}

            <div>
              <h2 className="font-semibold text-gray-800 mb-1">제안 배경</h2>
              <p className="text-sm text-gray-700 leading-relaxed">{proposal.background}</p>
            </div>
            <div>
              <h2 className="font-semibold text-gray-800 mb-1">주요 내용</h2>
              <p className="text-sm text-gray-700 leading-relaxed">{proposal.core_requests}</p>
            </div>
            <div>
              <h2 className="font-semibold text-gray-800 mb-1">기대 효과</h2>
              <p className="text-sm text-gray-700 leading-relaxed">{proposal.expected_effects}</p>
            </div>
            {proposal.related_laws.length > 0 && (
              <div>
                <h2 className="font-semibold text-gray-800 mb-2">관련 법령</h2>
                <div className="flex flex-wrap gap-2">
                  {proposal.related_laws.map((law, i) => (
                    <span key={i} className="px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded-full border border-blue-200">{law}</span>
                  ))}
                </div>
              </div>
            )}
            {download_url && (
              <a
                href={`${API_BASE}${download_url}`}
                download
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 transition"
              >
                <Download size={16} /> DOCX 다운로드
              </a>
            )}
          </div>
        ) : (
          <div className="bg-white rounded-2xl shadow-md p-6 text-center text-gray-400">제안서 데이터가 없습니다.</div>
        )}

        {/* ─── 법안 패널 ─── */}
        {showBill && bill && (
          <div className="bg-white rounded-2xl shadow-md border-2 border-purple-200 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs uppercase tracking-widest text-purple-500 font-semibold">정식 법안</span>
                <h2 className="text-xl font-bold text-gray-900 mt-1">{bill.bill_title}</h2>
                <p className="text-xs text-gray-500 mt-0.5">의안번호 {bill.bill_number} · {bill.proposer} · {bill.expected_committee}</p>
              </div>
              <button onClick={downloadBill} className="inline-flex items-center gap-2 rounded-full bg-gray-100 hover:bg-gray-200 px-4 py-2 text-sm font-semibold text-gray-700 transition">
                <Download size={15} /> 다운로드
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-1">제안이유</h3>
                <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">{bill.purpose}</p>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-1">주요내용</h3>
                <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">{bill.main_content}</p>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-2">조문</h3>
                <div className="space-y-2 bg-gray-50 rounded-xl p-4">
                  {bill.articles.map((art) => (
                    <div key={art.article_number} className="text-sm">
                      <span className="font-semibold text-gray-800">제{art.article_number}조 ({art.title}) </span>
                      <span className="text-gray-600">{art.content}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="text-sm">
                <span className="font-semibold text-gray-700">부칙 </span>
                <span className="text-gray-600">{bill.supplementary_provisions}</span>
              </div>

              {bill.related_laws.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-1">관련 법령</h3>
                  <div className="flex flex-wrap gap-2">
                    {bill.related_laws.map((l, i) => (
                      <span key={i} className="px-2 py-0.5 bg-purple-50 text-purple-700 text-xs rounded-full border border-purple-200">{l}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* AI 검토 의견 (localStorage에서 복원) */}
        {review && (
          <div className="bg-white rounded-2xl shadow-md p-6 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-gray-800">AI 검토 의견</h2>
              <span className="text-sm font-bold text-blue-600">타당성 {Math.round(review.validity_score * 100)}점</span>
            </div>
            {review.strengths?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-green-700 mb-1">강점</p>
                <ul className="text-sm text-gray-700 space-y-0.5">{review.strengths.map((s, i) => <li key={i}>✓ {s}</li>)}</ul>
              </div>
            )}
            {review.weaknesses?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-amber-700 mb-1">보완점</p>
                <ul className="text-sm text-gray-700 space-y-0.5">{review.weaknesses.map((w, i) => <li key={i}>△ {w}</li>)}</ul>
              </div>
            )}
          </div>
        )}

        {/* AI 개선 효과 비교 카드 */}
        {result.draft_analysis && analysis && (
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl border border-blue-200 p-5 shadow-sm space-y-3">
            <h2 className="font-semibold text-blue-900">🤖 AI 개선 효과</h2>
            <div className="grid grid-cols-2 gap-4">
              {/* 통과 확률 비교 */}
              <div className="bg-white rounded-xl p-4 space-y-2 border border-blue-100">
                <p className="text-xs text-gray-500">통과 예측</p>
                <div className="flex items-end gap-2">
                  <span className="text-xl font-bold text-gray-400">
                    {Math.round(result.draft_analysis.pass_probability * 100)}%
                  </span>
                  <span className="text-blue-500 text-sm mb-0.5">→</span>
                  <span className="text-2xl font-bold text-emerald-600">
                    {Math.round(analysis.pass_probability * 100)}%
                  </span>
                </div>
                {analysis.pass_probability > result.draft_analysis.pass_probability && (
                  <p className="text-xs text-emerald-600 font-medium">
                    +{Math.round((analysis.pass_probability - result.draft_analysis.pass_probability) * 100)}%p 개선
                  </p>
                )}
              </div>
              {/* 예상 소요일 비교 */}
              <div className="bg-white rounded-xl p-4 space-y-2 border border-blue-100">
                <p className="text-xs text-gray-500">예상 소요일</p>
                <div className="flex items-end gap-2">
                  <span className="text-xl font-bold text-gray-400">
                    {result.draft_analysis.expected_duration_days}일
                  </span>
                  <span className="text-blue-500 text-sm mb-0.5">→</span>
                  <span className="text-2xl font-bold text-purple-600">
                    {analysis.expected_duration_days}일
                  </span>
                </div>
                {analysis.expected_duration_days < result.draft_analysis.expected_duration_days && (
                  <p className="text-xs text-purple-600 font-medium">
                    {result.draft_analysis.expected_duration_days - analysis.expected_duration_days}일 단축
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* 분석 지표 */}
        {analysis && (
          <>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white rounded-2xl shadow-md p-5 text-center">
                <p className="text-xs text-gray-500 mb-1">통과 확률</p>
                <p className="text-3xl font-bold text-emerald-600">{Math.round(analysis.pass_probability * 100)}%</p>
              </div>
              <div className="bg-white rounded-2xl shadow-md p-5 text-center">
                <p className="text-xs text-gray-500 mb-1">예상 소요 기간</p>
                <p className="text-3xl font-bold text-purple-600">{analysis.expected_duration_days}일</p>
              </div>
            </div>

            {/* 예상 처리 경로 (KoBERT 활성화 시) */}
            {stagePredictions && (
              <div className="bg-white rounded-2xl shadow-md p-6 space-y-4">
                <h2 className="font-semibold text-gray-800">📋 예상 처리 경로</h2>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded-full text-sm font-medium border border-blue-100">
                    {stagePredictions.predicted_progress_stage}
                  </span>
                  <span className="text-gray-400 font-bold">→</span>
                  <span className="px-3 py-1.5 bg-emerald-50 text-emerald-700 rounded-full text-sm font-medium border border-emerald-100">
                    {stagePredictions.predicted_proc_result}
                  </span>
                  {stagePredictions.predicted_cmt_result && (
                    <>
                      <span className="text-gray-400 font-bold">→</span>
                      <span className="px-3 py-1.5 bg-purple-50 text-purple-700 rounded-full text-sm font-medium border border-purple-100">
                        위원회: {stagePredictions.predicted_cmt_result}
                      </span>
                    </>
                  )}
                </div>
                {stagePredictions.top_progress_stages.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-gray-500">단계별 예측 확률</p>
                    {stagePredictions.top_progress_stages.slice(0, 4).map((s, i) => (
                      <div key={i}>
                        <div className="flex justify-between text-xs text-gray-600 mb-0.5">
                          <span>{s.label}</span>
                          <span>{Math.round(s.probability * 100)}%</span>
                        </div>
                        <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-blue-400 to-blue-600 rounded-full"
                            style={{ width: `${Math.round(s.probability * 100)}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {analysis.visualization_data?.timeline && (
              <div className="bg-white rounded-2xl shadow-md p-6">
                <h2 className="font-semibold text-gray-800 mb-4">처리 단계별 예상 기간 (일)</h2>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={analysis.visualization_data.timeline}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis unit="일" />
                    <Tooltip formatter={(v: number) => `${v}일`} />
                    <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {analysis.similar_cases.length > 0 && (
              <div className="bg-white rounded-2xl shadow-md p-6">
                <h2 className="font-semibold text-gray-800 mb-4">유사 사례</h2>
                <div className="space-y-3">
                  {analysis.similar_cases.map((c, i) => (
                    <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl border border-gray-200">
                      <span className="text-sm text-gray-800">{c.title}</span>
                      <span className="text-xs font-semibold text-blue-600 bg-blue-50 px-2 py-1 rounded-full">
                        유사도 {Math.round(c.similarity * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(analysis.visualization_data?.committee_recommendations?.length ?? 0) > 0 && (
              <div className="bg-white rounded-2xl shadow-md p-6">
                <h2 className="font-semibold text-gray-800 mb-4">🏛️ 소관 위원회 추천</h2>
                <div className="space-y-3">
                  {analysis.visualization_data.committee_recommendations!.map((c, i) => (
                    <div key={i}>
                      <div className="flex justify-between items-center text-sm mb-1">
                        <span className="text-gray-800 font-medium">{c.committee}</span>
                        <span className="text-blue-600 font-semibold text-xs">
                          {Math.round(c.relevance * 100)}%
                        </span>
                      </div>
                      <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-blue-400 to-blue-600 rounded-full transition-all"
                          style={{ width: `${Math.round(c.relevance * 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-400 mt-3">
                  AI가 제안서 내용을 분석하여 가장 관련성 높은 상임위원회를 추천합니다.
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function formatBillText(bill: FormalBill): string {
  const lines: string[] = []
  lines.push('=' .repeat(60))
  lines.push(bill.bill_title)
  lines.push('=' .repeat(60))
  lines.push('')
  lines.push(`의안번호: ${bill.bill_number}`)
  lines.push(`제안자: ${bill.proposer}`)
  lines.push(`소관위원회: ${bill.expected_committee}`)
  lines.push('')
  lines.push('[제안이유]')
  lines.push(bill.purpose)
  lines.push('')
  lines.push('[주요내용]')
  lines.push(bill.main_content)
  lines.push('')
  lines.push('[법안 본문]')
  bill.articles.forEach((a) => {
    lines.push(`제${a.article_number}조(${a.title}) ${a.content}`)
  })
  lines.push('')
  lines.push('[부칙]')
  lines.push(bill.supplementary_provisions)
  if (bill.related_laws.length > 0) {
    lines.push('')
    lines.push('[관련 법령]')
    lines.push(bill.related_laws.join(', '))
  }
  return lines.join('\n')
}
