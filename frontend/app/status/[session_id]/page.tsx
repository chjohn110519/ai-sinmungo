'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { CheckCircle, Circle, Clock, AlertCircle, FileText, ExternalLink } from 'lucide-react'

interface StatusStep {
  step: number
  label: string
  done: boolean
}

interface SessionStatus {
  session_id: string
  status: string
  current_step: number
  current_label: string
  classification: string | null
  created_at: string | null
  proposal_title: string | null
  has_result: boolean
  steps: StatusStep[]
}

const CLASS_STYLE: Record<string, string> = {
  민원: 'bg-orange-100 text-orange-700 border-orange-200',
  제안: 'bg-blue-100 text-blue-700 border-blue-200',
  청원: 'bg-purple-100 text-purple-700 border-purple-200',
}

const STEP_ICONS = [
  '📥', '🔍', '🗂️', '📝', '✅', '🎉',
]

export default function StatusPage() {
  const params = useParams()
  const router = useRouter()
  const sessionId = params['session_id'] as string

  const [status, setStatus] = useState<SessionStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pollCount, setPollCount] = useState(0)

  const fetchStatus = useCallback(() => {
    fetch(`/api/session/${sessionId}/status`)
      .then((r) => {
        if (!r.ok) throw new Error('처리 현황을 찾을 수 없습니다.')
        return r.json()
      })
      .then((d) => { setStatus(d); setError(null) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [sessionId])

  // 미완료 상태면 5초마다 자동 폴링
  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  useEffect(() => {
    if (!status) return
    if (status.status === 'completed' || status.status === 'failed') return

    const timer = setTimeout(() => {
      fetchStatus()
      setPollCount((c) => c + 1)
    }, 5000)
    return () => clearTimeout(timer)
  }, [status, pollCount, fetchStatus])

  if (loading && !status) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <AlertCircle className="h-12 w-12 text-red-400 mx-auto" />
          <p className="text-red-500">{error}</p>
          <p className="text-sm text-gray-500">접수번호를 다시 확인해 주세요.</p>
          <button onClick={() => router.push('/')} className="text-blue-600 underline text-sm">홈으로</button>
        </div>
      </div>
    )
  }

  const isCompleted = status?.status === 'completed'
  const isFailed = status?.status === 'failed'
  const isProcessing = !isCompleted && !isFailed

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-white py-10 px-4">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* 헤더 */}
        <div className="text-center space-y-2">
          <p className="text-xs uppercase tracking-widest text-blue-500 font-semibold">민원 처리 현황</p>
          <h1 className="text-2xl font-bold text-gray-900">접수 상태를 확인하세요</h1>
          <p className="text-sm text-gray-500 font-mono bg-gray-100 px-3 py-1 rounded-lg inline-block">
            접수번호: {sessionId}
          </p>
        </div>

        {/* 상태 배너 */}
        <div className={`rounded-2xl p-5 flex items-center gap-4 ${
          isCompleted ? 'bg-emerald-50 border border-emerald-200'
          : isFailed ? 'bg-red-50 border border-red-200'
          : 'bg-blue-50 border border-blue-200'
        }`}>
          {isCompleted ? (
            <CheckCircle className="h-8 w-8 text-emerald-500 flex-shrink-0" />
          ) : isFailed ? (
            <AlertCircle className="h-8 w-8 text-red-500 flex-shrink-0" />
          ) : (
            <Clock className="h-8 w-8 text-blue-500 flex-shrink-0 animate-pulse" />
          )}
          <div>
            <p className={`font-bold text-lg ${isCompleted ? 'text-emerald-700' : isFailed ? 'text-red-700' : 'text-blue-700'}`}>
              {status?.current_label}
            </p>
            <p className="text-sm text-gray-600">
              {isCompleted ? '모든 처리가 완료되었습니다. 결과를 확인해 보세요.'
               : isFailed ? '처리 중 문제가 발생했습니다. 다시 제출해 주세요.'
               : '현재 AI가 민원을 분석하고 있습니다. 잠시만 기다려 주세요.'}
            </p>
          </div>
          {status?.classification && (
            <span className={`ml-auto px-3 py-1 rounded-full text-sm font-semibold border flex-shrink-0 ${CLASS_STYLE[status.classification] || 'bg-gray-100 text-gray-600'}`}>
              {status.classification}
            </span>
          )}
        </div>

        {/* 단계 스텝퍼 */}
        <div className="bg-white rounded-2xl shadow-md p-6">
          <h2 className="font-semibold text-gray-800 mb-5">처리 단계</h2>
          <div className="relative">
            {/* 연결선 */}
            <div className="absolute left-5 top-0 bottom-0 w-0.5 bg-gray-200" style={{ top: '20px', bottom: '20px' }} />

            <div className="space-y-5">
              {status?.steps.map((step, i) => {
                const isCurrent = step.step === status.current_step && isProcessing
                return (
                  <div key={step.step} className="relative flex items-start gap-4 pl-2">
                    {/* 아이콘 */}
                    <div className={`relative z-10 flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-lg border-2 ${
                      step.done && !isCurrent
                        ? 'bg-emerald-500 border-emerald-500 text-white'
                        : isCurrent
                        ? 'bg-blue-500 border-blue-500 text-white animate-pulse'
                        : 'bg-white border-gray-300 text-gray-400'
                    }`}>
                      {step.done && !isCurrent ? (
                        <CheckCircle className="h-5 w-5" />
                      ) : isCurrent ? (
                        <Clock className="h-5 w-5" />
                      ) : (
                        <Circle className="h-5 w-5" />
                      )}
                    </div>

                    {/* 텍스트 */}
                    <div className="pt-2">
                      <p className={`font-medium ${
                        step.done ? 'text-gray-900'
                        : isCurrent ? 'text-blue-700'
                        : 'text-gray-400'
                      }`}>
                        {STEP_ICONS[i]} {step.label}
                      </p>
                      {step.done && (
                        <p className="text-xs text-emerald-600 mt-0.5">완료</p>
                      )}
                      {isCurrent && (
                        <p className="text-xs text-blue-500 mt-0.5">처리 중…</p>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* 제안서 제목 (있을 경우) */}
        {status?.proposal_title && (
          <div className="bg-white rounded-2xl shadow-md p-5 flex items-start gap-3">
            <FileText className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs text-gray-500 mb-0.5">생성된 정책 제안서</p>
              <p className="font-semibold text-gray-800">{status.proposal_title}</p>
            </div>
          </div>
        )}

        {/* 액션 버튼 */}
        <div className="flex flex-col sm:flex-row gap-3">
          {isCompleted && (
            <Link
              href={`/result/${sessionId}`}
              className="flex-1 flex items-center justify-center gap-2 rounded-full bg-blue-600 hover:bg-blue-700 px-6 py-3 text-sm font-semibold text-white transition shadow-lg"
            >
              <ExternalLink size={16} />
              결과 상세 보기
            </Link>
          )}
          <button
            onClick={fetchStatus}
            className="flex-1 rounded-full border border-gray-300 bg-white hover:bg-gray-50 px-6 py-3 text-sm font-semibold text-gray-700 transition"
          >
            현황 새로고침
          </button>
          <Link
            href="/"
            className="flex-1 flex items-center justify-center rounded-full border border-blue-200 bg-blue-50 hover:bg-blue-100 px-6 py-3 text-sm font-semibold text-blue-700 transition"
          >
            새 민원 접수
          </Link>
        </div>

        {/* 접수 시각 */}
        {status?.created_at && (
          <p className="text-center text-xs text-gray-400">
            접수 시각: {new Date(status.created_at).toLocaleString('ko-KR')}
          </p>
        )}

        {/* 자동 폴링 안내 */}
        {isProcessing && (
          <p className="text-center text-xs text-blue-400 animate-pulse">
            5초마다 자동으로 현황을 업데이트합니다…
          </p>
        )}
      </div>
    </div>
  )
}
