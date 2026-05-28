'use client'

import { useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Send, Mic, MicOff, CheckCircle, Circle, ChevronRight, FileText, Paperclip, X, Image as ImageIcon, Users, Download, Sparkles, ArrowRight, SkipForward } from 'lucide-react'
import ClusterStatus from './ClusterStatus'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'
const STORAGE_KEY = 'complaint_sessions'

type Stage = 'idle' | 'questioning' | 'improving' | 'aggregated'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Ctx = Record<string, any>

interface ClarifyingQuestion {
  question: string
  hint: string
}

interface QuestioningState {
  session_id: string
  classification: string
  responsible_dept: string
  confidence: number
  questions: ClarifyingQuestion[]
  original_message?: string
  topic?: string
  keywords?: string[]
  cluster_id?: string | null
  cluster_count?: number
  cluster_threshold?: number
  cluster_triggered?: boolean
  ctx?: Ctx
}

interface Improvement {
  id: number
  category: string       // '법적근거강화' | '데이터보완' | '대상확장' | '제도적맥락' | '표현개선'
  suggestion: string
  impact: string
  requires_info?: string | null
}

interface TrendingKeyword {
  keyword: string
  total_count: number
  cluster_id?: string | null
  topic?: string | null
}

interface AnalysisPreview {
  feasibility_score: number
  pass_probability: number
  expected_duration_days: number
  visualization_data: {
    timeline?: Array<{ name: string; value: number }>
    committee_recommendations?: Array<{ committee: string; relevance: number }>
  }
}

interface ImprovingState {
  session_id: string
  classification: string
  responsible_dept: string
  improvements: Improvement[]
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  draft_proposal?: Record<string, any>
  analysis?: AnalysisPreview | null
  cluster_id?: string | null
  cluster_topic?: string
  cluster_keywords?: string[]
  cluster_count?: number
  cluster_threshold?: number
  cluster_triggered?: boolean
  cluster_progress_percent?: number
  proposal_id?: string | null
  receipt_number?: string
  expected_days?: number
  download_url?: string
  trending_keywords?: TrendingKeyword[]
  ctx?: Ctx
}

// 하위 호환용 (개선 이전 세션 처리)
interface AggregatedState {
  session_id: string
  classification: string
  responsible_dept: string
  cluster_id?: string | null
  cluster_topic?: string
  cluster_keywords?: string[]
  cluster_count?: number
  cluster_threshold?: number
  cluster_triggered?: boolean
  cluster_progress_percent?: number
  proposal_id?: string | null
  receipt_number?: string
  expected_days?: number
  download_url?: string
  trending_keywords?: TrendingKeyword[]
  ctx?: Ctx
}

interface AttachmentPreview {
  id: string
  name: string
  type: string
  size: number
  uploading: boolean
  error?: string
}

// 카테고리별 색상 + 이모지 매핑
const CATEGORY_STYLE: Record<string, { bg: string; border: string; badge: string; text: string; icon: string }> = {
  '법적근거강화': { bg: 'bg-blue-50',   border: 'border-blue-200',   badge: 'bg-blue-100 text-blue-700',   text: 'text-blue-800',   icon: '⚖️' },
  '데이터보완':   { bg: 'bg-green-50',  border: 'border-green-200',  badge: 'bg-green-100 text-green-700',  text: 'text-green-800',  icon: '📊' },
  '대상확장':     { bg: 'bg-purple-50', border: 'border-purple-200', badge: 'bg-purple-100 text-purple-700', text: 'text-purple-800', icon: '👥' },
  '제도적맥락':   { bg: 'bg-amber-50',  border: 'border-amber-200',  badge: 'bg-amber-100 text-amber-700',  text: 'text-amber-800',  icon: '🌏' },
  '표현개선':     { bg: 'bg-pink-50',   border: 'border-pink-200',   badge: 'bg-pink-100 text-pink-700',    text: 'text-pink-800',   icon: '✏️' },
}

function getStyle(category: string) {
  return CATEGORY_STYLE[category] ?? {
    bg: 'bg-gray-50', border: 'border-gray-200',
    badge: 'bg-gray-100 text-gray-700', text: 'text-gray-800', icon: '💡',
  }
}

function fileIcon(type: string) {
  if (type.startsWith('image/')) return <ImageIcon size={14} />
  return <FileText size={14} />
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

function persistSession(sid: string) {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') as string[]
    if (!stored.includes(sid)) {
      stored.unshift(sid)
      localStorage.setItem(STORAGE_KEY, JSON.stringify(stored.slice(0, 50)))
    }
  } catch {}
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function upsertComplaintSummary(summary: { session_id: string; title: string | null; classification: string | null; status: string; created_at: string }) {
  try {
    const summaries = JSON.parse(localStorage.getItem('complaint_summaries') || '[]') as typeof summary[]
    const filtered = summaries.filter(s => s.session_id !== summary.session_id)
    localStorage.setItem('complaint_summaries', JSON.stringify([summary, ...filtered].slice(0, 50)))
  } catch {}
}

export default function ConversationBox() {
  const router = useRouter()

  const [stage, setStage] = useState<Stage>('idle')
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [answerRecordingIdx, setAnswerRecordingIdx] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Stage-specific state
  const [questioningData, setQuestioningData] = useState<QuestioningState | null>(null)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [improvingData, setImprovingData] = useState<ImprovingState | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [userNote, setUserNote] = useState('')
  const [aggregatedData, setAggregatedData] = useState<AggregatedState | null>(null)

  // Attachments
  const [attachments, setAttachments] = useState<AttachmentPreview[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])

  const sessionId = questioningData?.session_id || improvingData?.session_id || aggregatedData?.session_id || null

  // ── TURN 1: 초기 메시지 전송 ───────────────────────────────────────────────
  async function handleStart() {
    if (!input.trim() && attachments.filter(a => a.id && !a.error).length === 0) return
    setIsLoading(true)
    setError(null)
    try {
      const attachment_ids = attachments.filter(a => a.id && !a.error).map(a => a.id)
      const res = await fetch(`${API_BASE}/api/conversation/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input.trim(), attachment_ids }),
      })
      if (!res.ok) throw new Error(await res.text())
      const data: QuestioningState = await res.json()
      setQuestioningData(data)
      setAnswers({})
      setStage('questioning')
      persistSession(data.session_id)
      upsertComplaintSummary({
        session_id: data.session_id,
        title: null,
        classification: data.classification,
        status: 'in_progress',
        created_at: new Date().toISOString(),
      })
      setInput('')
      setAttachments([])
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '오류가 발생했습니다.')
    } finally {
      setIsLoading(false)
    }
  }

  // ── TURN 2: 질문 답변 전송 → improving 단계 진입 ────────────────────────────
  async function handleAnswer() {
    if (!questioningData) return
    setIsLoading(true)
    setError(null)
    try {
      const stringAnswers: Record<string, string> = {}
      Object.entries(answers).forEach(([k, v]) => { stringAnswers[String(k)] = v })
      const res = await fetch(`${API_BASE}/api/conversation/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: questioningData.session_id,
          answers: stringAnswers,
          ctx: questioningData.ctx,   // 서버리스용: 컨텍스트 전달
        }),
      })
      if (!res.ok) throw new Error(await res.text())
      const data: ImprovingState = await res.json()
      setImprovingData(data)
      setSelectedIds(new Set())
      setUserNote('')
      setStage('improving')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '오류가 발생했습니다.')
    } finally {
      setIsLoading(false)
    }
  }

  // ── TURN 3: 개선안 수락 → 최종 제안서 → result 페이지 ─────────────────────
  async function handleFinalize(skipAll = false) {
    if (!improvingData) return
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/conversation/finalize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: improvingData.session_id,
          accepted_improvement_ids: skipAll ? [] : Array.from(selectedIds),
          user_note: userNote || null,
          ctx: improvingData.ctx,
        }),
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()

      // result 페이지에 데이터 전달 (window + sessionStorage 이중 저장)
      const sessionResult = {
        session: {
          session_id: data.session_id,
          status: 'completed',
          final_classification: data.classification,
        },
        proposal: data.final_proposal,
        analysis: {
          similar_cases: data.similar_cases || [],
          pass_probability: data.analysis?.pass_probability ?? 0,
          expected_duration_days: data.analysis?.expected_duration_days ?? 14,
          feasibility_score: data.analysis?.feasibility_score ?? 0,
          visualization_data: data.analysis?.visualization_data || { timeline: [] },
        },
        // 초안 수치 — answer 단계에서 받아둔 analysis_preview를 우선 사용
        draft_analysis: data.draft_analysis || improvingData?.analysis || null,
        review: data.review || null,
        download_url: data.download_url || null,
      }
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ;(window as any).__pendingResult = { sid: data.session_id, data: sessionResult }
        sessionStorage.setItem('__pending_result',
          JSON.stringify({ sid: data.session_id, data: sessionResult }))
        localStorage.setItem(`result_${data.session_id}`, JSON.stringify(sessionResult))
      } catch {}

      upsertComplaintSummary({
        session_id: data.session_id,
        title: data.final_proposal?.title || null,
        classification: data.classification,
        status: 'completed',
        created_at: new Date().toISOString(),
      })

      router.push(`/result/${data.session_id}`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '오류가 발생했습니다.')
    } finally {
      setIsLoading(false)
    }
  }

  // ── 파일 업로드 ──────────────────────────────────────────────────────────────
  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    for (const file of files) {
      const preview: AttachmentPreview = {
        id: '', name: file.name, type: file.type,
        size: file.size, uploading: true,
      }
      setAttachments(prev => [...prev, preview])
      try {
        const formData = new FormData()
        formData.append('file', file)
        if (sessionId) formData.append('session_id', sessionId)
        const res = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: formData })
        if (!res.ok) throw new Error(await res.text())
        const data = await res.json()
        setAttachments(prev => prev.map((a) =>
          a.name === file.name && a.uploading ? { ...a, id: data.attachment_id, uploading: false } : a
        ))
      } catch {
        setAttachments(prev => prev.map((a) =>
          a.name === file.name && a.uploading ? { ...a, uploading: false, error: '업로드 실패' } : a
        ))
      }
    }
    e.target.value = ''
  }

  // ── 음성 녹음 ─────────────────────────────────────────────────────────────
  async function toggleRecording() {
    if (isRecording) {
      mediaRecorderRef.current?.stop()
      setIsRecording(false)
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      // 브라우저별 지원 mimeType 자동 선택 (Safari는 audio/webm 미지원)
      const mimeType = ['audio/webm', 'audio/ogg', 'audio/mp4', ''].find(
        m => m === '' || MediaRecorder.isTypeSupported(m)
      ) ?? ''
      const mr = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream)

      audioChunksRef.current = []
      mr.ondataavailable = e => { if (e.data.size > 0) audioChunksRef.current.push(e.data) }
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        if (audioChunksRef.current.length === 0) {
          setError('녹음된 음성이 없습니다. 다시 시도해 주세요.')
          return
        }
        const blob = new Blob(audioChunksRef.current, { type: mr.mimeType || 'audio/webm' })
        const ext = (mr.mimeType || 'audio/webm').includes('mp4') ? 'mp4'
          : (mr.mimeType || '').includes('ogg') ? 'ogg' : 'webm'
        const formData = new FormData()
        formData.append('audio', blob, `recording.${ext}`)
        setIsTranscribing(true)
        try {
          const res = await fetch(`${API_BASE}/api/voice/transcribe`, { method: 'POST', body: formData })
          if (res.ok) {
            const data = await res.json()
            setInput(prev => prev + (prev ? ' ' : '') + data.transcript)
          } else {
            const err = await res.json().catch(() => ({ detail: '음성 인식 실패' }))
            setError(err.detail || '음성 인식에 실패했습니다.')
          }
        } catch {
          setError('음성 인식 서버에 연결할 수 없습니다.')
        } finally {
          setIsTranscribing(false)
        }
      }
      mr.start(250) // 250ms마다 ondataavailable 발생 (청크 누락 방지)
      mediaRecorderRef.current = mr
      setIsRecording(true)
    } catch {
      setError('마이크 접근 권한이 필요합니다.')
    }
  }

  // ── 답변 텍스트에어리어용 음성 녹음 ──────────────────────────────────────────
  async function toggleAnswerRecording(idx: number) {
    if (isRecording) {
      mediaRecorderRef.current?.stop()
      setIsRecording(false)
      setAnswerRecordingIdx(null)
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mimeType = ['audio/webm', 'audio/ogg', 'audio/mp4', ''].find(
        m => m === '' || MediaRecorder.isTypeSupported(m)
      ) ?? ''
      const mr = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream)
      audioChunksRef.current = []
      mr.ondataavailable = e => { if (e.data.size > 0) audioChunksRef.current.push(e.data) }
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        if (audioChunksRef.current.length === 0) {
          setError('녹음된 음성이 없습니다. 다시 시도해 주세요.')
          setAnswerRecordingIdx(null)
          return
        }
        const blob = new Blob(audioChunksRef.current, { type: mr.mimeType || 'audio/webm' })
        const ext = (mr.mimeType || 'audio/webm').includes('mp4') ? 'mp4'
          : (mr.mimeType || '').includes('ogg') ? 'ogg' : 'webm'
        const formData = new FormData()
        formData.append('audio', blob, `recording.${ext}`)
        setIsTranscribing(true)
        try {
          const res = await fetch(`${API_BASE}/api/voice/transcribe`, { method: 'POST', body: formData })
          if (res.ok) {
            const data = await res.json()
            setAnswers(prev => ({
              ...prev,
              [idx]: (prev[idx] ? prev[idx] + ' ' : '') + data.transcript,
            }))
          } else {
            const err = await res.json().catch(() => ({ detail: '음성 인식 실패' }))
            setError(err.detail || '음성 인식에 실패했습니다.')
          }
        } catch {
          setError('음성 인식 서버에 연결할 수 없습니다.')
        } finally {
          setIsTranscribing(false)
          setAnswerRecordingIdx(null)
        }
      }
      mr.start(250)
      mediaRecorderRef.current = mr
      setIsRecording(true)
      setAnswerRecordingIdx(idx)
    } catch {
      setError('마이크 접근 권한이 필요합니다.')
    }
  }

  function toggleSelectId(id: number) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  function resetAll() {
    setStage('idle')
    setInput('')
    setQuestioningData(null)
    setImprovingData(null)
    setAggregatedData(null)
    setAnswers({})
    setSelectedIds(new Set())
    setUserNote('')
    setAttachments([])
    setError(null)
  }

  // ── Stage 진행 표시 ────────────────────────────────────────────────────────
  const stages = [
    { key: 'idle', label: '민원 작성' },
    { key: 'questioning', label: 'AI 질문' },
    { key: 'improving', label: '개선안 선택' },
    { key: 'aggregated', label: '결과 확인' },
  ]
  const currentStageIdx = stages.findIndex(s => s.key === stage)

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      {/* Progress bar */}
      <div className="flex items-center gap-1 mb-6">
        {stages.map((s, i) => (
          <div key={s.key} className="flex items-center flex-1">
            <div className={`flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full transition-all ${
              i < currentStageIdx ? 'bg-blue-100 text-blue-700' :
              i === currentStageIdx ? 'bg-blue-600 text-white' :
              'bg-gray-100 text-gray-400'
            }`}>
              {i < currentStageIdx ? <CheckCircle size={12} /> : <Circle size={12} />}
              {s.label}
            </div>
            {i < stages.length - 1 && (
              <ChevronRight size={14} className={`mx-1 flex-shrink-0 ${i < currentStageIdx ? 'text-blue-400' : 'text-gray-300'}`} />
            )}
          </div>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-400 hover:text-red-600">✕</button>
        </div>
      )}

      {/* ── STAGE: idle ─────────────────────────────────────────────────────── */}
      {stage === 'idle' && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-800">민원인지 청원인지 몰라도 됩니다</h2>
            <p className="text-sm text-gray-500 mt-1">
              하고 싶은 말을 자유롭게 쓰세요. AI가 자동으로 분류하고, 같은 의견이 모이면 공식 제안서가 만들어집니다.
            </p>
          </div>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="예: 우리 동네 도로가 너무 위험합니다. 보행자 안전을 위한 개선이 필요합니다..."
            rows={5}
            className="w-full border border-gray-300 rounded-lg p-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            onKeyDown={e => { if (e.key === 'Enter' && e.metaKey) handleStart() }}
          />

          {/* Attachments */}
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {attachments.map((a, i) => (
                <div key={i} className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full border ${a.error ? 'border-red-300 bg-red-50' : 'border-gray-200 bg-gray-50'}`}>
                  {fileIcon(a.type)}
                  <span className="max-w-[120px] truncate">{a.name}</span>
                  <span className="text-gray-400">{formatBytes(a.size)}</span>
                  {a.uploading && <span className="text-blue-500">↑</span>}
                  {a.error && <span className="text-red-500">!</span>}
                  <button onClick={() => setAttachments(prev => prev.filter((_, j) => j !== i))}>
                    <X size={12} className="text-gray-400 hover:text-gray-700" />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center gap-2">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 border border-gray-200"
              title="파일 첨부"
            >
              <Paperclip size={18} />
            </button>
            <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileSelect}
              accept=".pdf,.doc,.docx,.txt,image/*" />
            <button
              onClick={toggleRecording}
              disabled={isTranscribing}
              className={`p-2 rounded-lg border transition-colors ${
                isRecording ? 'bg-red-500 text-white border-red-500 animate-pulse'
                : isTranscribing ? 'bg-blue-100 text-blue-500 border-blue-200'
                : 'text-gray-500 hover:bg-gray-100 border-gray-200'
              }`}
              title={isRecording ? '녹음 중지' : isTranscribing ? '음성 변환 중...' : '음성 입력'}
            >
              {isTranscribing
                ? <span className="text-xs font-medium px-0.5">변환중</span>
                : isRecording ? <MicOff size={18} /> : <Mic size={18} />
              }
            </button>
            <div className="flex-1" />
            <button
              onClick={handleStart}
              disabled={isLoading || (!input.trim() && attachments.filter(a => a.id).length === 0)}
              className="flex items-center gap-2 px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'AI 분류 중…' : '제출하기'}
              {!isLoading && <Send size={15} />}
            </button>
          </div>
        </div>
      )}

      {/* ── STAGE: questioning ────────────────────────────────────────────────── */}
      {stage === 'questioning' && questioningData && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-5">
          {/* Classification badge */}
          <div className="flex items-center gap-3">
            <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
              questioningData.classification === '민원' ? 'bg-orange-100 text-orange-700' :
              questioningData.classification === '제안' ? 'bg-blue-100 text-blue-700' :
              'bg-purple-100 text-purple-700'
            }`}>
              {questioningData.classification}
            </span>
            <span className="text-sm text-gray-500">
              {questioningData.responsible_dept} · 신뢰도 {Math.round(questioningData.confidence * 100)}%
            </span>
          </div>

          {/* 집계 현황 (제안/청원인 경우) */}
          {questioningData.cluster_id && questioningData.classification !== '민원' && (
            <ClusterStatus
              clusterId={questioningData.cluster_id}
              topic={questioningData.topic || '기타'}
              keywords={questioningData.keywords || []}
              classification={questioningData.classification}
              count={questioningData.cluster_count ?? 1}
              threshold={questioningData.cluster_threshold ?? 50}
              triggered={questioningData.cluster_triggered ?? false}
              progressPercent={Math.round(((questioningData.cluster_count ?? 1) / (questioningData.cluster_threshold ?? 50)) * 100)}
            />
          )}

          {/* 접수한 민원 요약 */}
          {questioningData.original_message && (
            <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3">
              <p className="text-xs font-semibold text-blue-500 mb-1">📋 접수한 내용</p>
              <p className="text-sm text-blue-800 line-clamp-2 leading-relaxed">
                {questioningData.original_message}
              </p>
            </div>
          )}

          <div>
            <h2 className="text-base font-semibold text-gray-800 mb-1">
              내용을 바탕으로 몇 가지 여쭤볼게요
            </h2>
            <p className="text-sm text-gray-500">답변할수록 제안서 품질이 높아집니다. 모르는 항목은 건너뛰세요.</p>
          </div>

          <div className="space-y-3">
            {questioningData.questions.map((q, i) => (
              <div key={i} className="bg-gray-50 rounded-xl border border-gray-100 p-4 space-y-2">
                <div className="flex items-start gap-2.5">
                  <span className="flex-shrink-0 w-5 h-5 bg-blue-600 text-white rounded-full text-xs flex items-center justify-center font-bold mt-0.5">
                    {i + 1}
                  </span>
                  <label className="text-sm font-medium text-gray-800 leading-snug">
                    {q.question}
                  </label>
                </div>
                <div className="relative">
                  <textarea
                    value={answers[i] || ''}
                    onChange={e => setAnswers(prev => ({ ...prev, [i]: e.target.value }))}
                    placeholder={
                      isTranscribing && answerRecordingIdx === i
                        ? '음성 인식 중…'
                        : isRecording && answerRecordingIdx === i
                        ? '🎙 녹음 중… (버튼을 눌러 중지)'
                        : q.hint || '답변을 입력하세요 (선택)'
                    }
                    rows={2}
                    className="w-full border border-gray-200 rounded-lg p-2.5 pr-10 text-sm resize-none bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 placeholder:text-gray-400"
                  />
                  <button
                    type="button"
                    onClick={() => toggleAnswerRecording(i)}
                    disabled={isRecording && answerRecordingIdx !== i}
                    title={isRecording && answerRecordingIdx === i ? '녹음 중지' : '음성으로 답변'}
                    className={`absolute right-2 bottom-2 p-1.5 rounded-full transition-colors disabled:opacity-30 ${
                      isRecording && answerRecordingIdx === i
                        ? 'bg-red-100 hover:bg-red-200'
                        : 'hover:bg-gray-200'
                    }`}
                  >
                    {isTranscribing && answerRecordingIdx === i ? (
                      <Mic size={14} className="text-blue-500 animate-pulse" />
                    ) : isRecording && answerRecordingIdx === i ? (
                      <MicOff size={14} className="text-red-500" />
                    ) : (
                      <Mic size={14} className="text-gray-400" />
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between pt-2">
            <button onClick={resetAll} className="text-sm text-gray-400 hover:text-gray-600">
              ← 처음으로
            </button>
            <button
              onClick={handleAnswer}
              disabled={isLoading}
              className="flex items-center gap-2 px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {isLoading ? '초안 작성 중…' : '답변 제출'}
              {!isLoading && <Send size={15} />}
            </button>
          </div>
        </div>
      )}

      {/* ── STAGE: improving ─────────────────────────────────────────────────── */}
      {stage === 'improving' && improvingData && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-5">
          {/* 헤더 */}
          <div className="flex items-center gap-3">
            <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
              improvingData.classification === '민원' ? 'bg-orange-100 text-orange-700' :
              improvingData.classification === '제안' ? 'bg-blue-100 text-blue-700' :
              'bg-purple-100 text-purple-700'
            }`}>
              {improvingData.classification}
            </span>
            <span className="text-sm text-gray-500">{improvingData.responsible_dept}</span>
          </div>

          {/* 초안 제안서 미리보기 */}
          {improvingData.draft_proposal?.title && (
            <div className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3">
              <p className="text-xs font-semibold text-gray-400 mb-0.5">📄 초안 제안서</p>
              <p className="text-sm font-medium text-gray-800 line-clamp-1">
                {improvingData.draft_proposal.title as string}
              </p>
            </div>
          )}

          {/* AI 사전 분석 — 통과 확률 + 위원회 추천 */}
          {improvingData.analysis && (
            <div className="rounded-xl border border-blue-100 bg-blue-50/60 px-4 py-4 space-y-3">
              <p className="text-xs font-semibold text-blue-600 uppercase tracking-wider">🤖 AI 사전 분석</p>

              {/* 점수 행 */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-white rounded-lg px-3 py-2 text-center border border-blue-100">
                  <p className="text-xs text-gray-500 mb-0.5">실현 가능성</p>
                  <p className="text-lg font-bold text-blue-600">
                    {Math.round(improvingData.analysis.feasibility_score * 100)}%
                  </p>
                </div>
                <div className="bg-white rounded-lg px-3 py-2 text-center border border-blue-100">
                  <p className="text-xs text-gray-500 mb-0.5">통과 확률</p>
                  <p className="text-lg font-bold text-emerald-600">
                    {Math.round(improvingData.analysis.pass_probability * 100)}%
                  </p>
                </div>
              </div>

              {/* 소관 위원회 추천 */}
              {(improvingData.analysis.visualization_data?.committee_recommendations?.length ?? 0) > 0 && (
                <div className="space-y-1.5">
                  <p className="text-xs font-semibold text-gray-600">🏛️ 소관 위원회 추천</p>
                  {improvingData.analysis.visualization_data!.committee_recommendations!.slice(0, 3).map((c, i) => (
                    <div key={i}>
                      <div className="flex justify-between items-center text-xs mb-0.5">
                        <span className="text-gray-700 font-medium">{c.committee}</span>
                        <span className="text-blue-600 font-semibold">{Math.round(c.relevance * 100)}%</span>
                      </div>
                      <div className="w-full h-1.5 bg-blue-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-blue-400 to-blue-600 rounded-full"
                          style={{ width: `${Math.round(c.relevance * 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 안내 텍스트 */}
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Sparkles size={16} className="text-blue-500" />
              <h2 className="text-base font-semibold text-gray-800">
                AI가 통과 확률을 높일 수 있는 개선안을 분석했습니다
              </h2>
            </div>
            <p className="text-sm text-gray-500">
              적용할 항목을 선택하면 AI가 제안서를 자동으로 보완합니다. 건너뛰어도 제출은 가능합니다.
            </p>
          </div>

          {/* 개선안 카드 */}
          {improvingData.improvements.length > 0 ? (
            <div className="space-y-3">
              {improvingData.improvements.map((imp) => {
                const style = getStyle(imp.category)
                const selected = selectedIds.has(imp.id)
                return (
                  <button
                    key={imp.id}
                    type="button"
                    onClick={() => toggleSelectId(imp.id)}
                    className={`w-full text-left rounded-xl border-2 p-4 transition-all cursor-pointer ${
                      selected
                        ? `${style.bg} ${style.border} shadow-sm`
                        : 'bg-white border-gray-100 hover:border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {/* 체크박스 */}
                      <div className={`mt-0.5 flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                        selected ? 'bg-blue-600 border-blue-600' : 'border-gray-300 bg-white'
                      }`}>
                        {selected && (
                          <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 12 12">
                            <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        {/* 카테고리 배지 */}
                        <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full mb-2 ${style.badge}`}>
                          <span>{style.icon}</span>
                          {imp.category}
                        </span>
                        {/* 제안 내용 */}
                        <p className="text-sm text-gray-800 leading-relaxed mb-1.5">
                          {imp.suggestion}
                        </p>
                        {/* 기대 효과 */}
                        <p className={`text-xs font-medium flex items-center gap-1 ${style.text}`}>
                          <ArrowRight size={11} />
                          {imp.impact}
                        </p>
                        {/* 추가 정보 필요 여부 */}
                        {imp.requires_info && (
                          <p className="text-xs text-amber-600 mt-1.5 bg-amber-50 rounded px-2 py-1">
                            💬 {imp.requires_info}
                          </p>
                        )}
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          ) : (
            <div className="text-center py-6 text-gray-400 text-sm">
              개선안이 없습니다. 아래 버튼으로 제출할 수 있습니다.
            </div>
          )}

          {/* 선택 요약 */}
          {selectedIds.size > 0 && (
            <div className="flex items-center gap-2 text-sm text-blue-700 bg-blue-50 rounded-lg px-3 py-2">
              <CheckCircle size={14} className="flex-shrink-0" />
              <span>{selectedIds.size}개 항목 선택됨 — AI가 해당 부분을 보완하여 최종 제안서를 작성합니다.</span>
            </div>
          )}

          {/* 추가 메모 */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1.5">
              추가 메모 <span className="font-normal text-gray-400">(선택)</span>
            </label>
            <textarea
              value={userNote}
              onChange={e => setUserNote(e.target.value)}
              placeholder="담당자에게 전달할 추가 정보나 요청사항을 입력하세요..."
              rows={2}
              className="w-full border border-gray-200 rounded-lg p-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 placeholder:text-gray-400"
            />
          </div>

          {/* 버튼 영역 */}
          <div className="flex items-center justify-between pt-1">
            <button onClick={resetAll} className="text-sm text-gray-400 hover:text-gray-600">
              ← 처음으로
            </button>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleFinalize(true)}
                disabled={isLoading}
                className="flex items-center gap-1.5 px-4 py-2 text-sm text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
                title="개선안 없이 초안 그대로 제출"
              >
                <SkipForward size={14} />
                건너뛰기
              </button>
              <button
                onClick={() => handleFinalize(false)}
                disabled={isLoading}
                className="flex items-center gap-2 px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {isLoading
                  ? '최종 제안서 작성 중…'
                  : selectedIds.size > 0
                    ? `${selectedIds.size}개 적용하여 완성하기`
                    : '개선안 없이 제출하기'
                }
                {!isLoading && <ArrowRight size={15} />}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── STAGE: aggregated (하위 호환 — 구 세션 처리) ─────────────────────── */}
      {stage === 'aggregated' && aggregatedData && (
        <div className="space-y-4">
          {/* 제안/청원: 집적 현황 */}
          {aggregatedData.cluster_id ? (
            <>
              {/* 접수 확인 헤더 */}
              <div className="bg-gradient-to-r from-blue-600 to-blue-700 rounded-xl p-6 text-white">
                <div className="flex items-center gap-2 mb-1">
                  <CheckCircle size={20} />
                  <span className="font-semibold text-lg">의견이 접수되었습니다!</span>
                </div>
                <p className="text-blue-200 text-sm">
                  {aggregatedData.cluster_count}번째로 같은 방향의 의견을 보태셨습니다
                </p>
              </div>

              {/* 집적 현황 카드 */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-gray-800">📊 집적 현황</h3>
                  {aggregatedData.cluster_topic && (
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      aggregatedData.classification === '제안' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'
                    }`}>
                      {aggregatedData.cluster_topic}
                    </span>
                  )}
                </div>

                {/* 진행바 */}
                <div>
                  <div className="flex justify-between text-xs text-gray-500 mb-1.5">
                    <span className="font-medium text-blue-600">{aggregatedData.cluster_count?.toLocaleString()}명 참여</span>
                    <span>목표 {aggregatedData.cluster_threshold?.toLocaleString()}명</span>
                  </div>
                  <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-400 to-blue-600 rounded-full transition-all"
                      style={{ width: `${aggregatedData.cluster_progress_percent ?? 0}%` }}
                    />
                  </div>
                  {!aggregatedData.cluster_triggered ? (
                    <p className="text-xs text-gray-500 mt-1.5">
                      {((aggregatedData.cluster_threshold ?? 0) - (aggregatedData.cluster_count ?? 0)).toLocaleString()}명이 더 참여하면 AI가 공식 제안서를 자동 생성합니다
                    </p>
                  ) : (
                    <p className="text-xs text-green-700 mt-1.5 font-semibold flex items-center gap-1">
                      <CheckCircle size={12} /> 공식 제안서가 생성되었습니다!
                    </p>
                  )}
                </div>

                {/* 키워드 */}
                {aggregatedData.cluster_keywords && aggregatedData.cluster_keywords.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {aggregatedData.cluster_keywords.slice(0, 8).map((kw, i) => (
                      <span key={i} className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full">{kw}</span>
                    ))}
                  </div>
                )}

                {/* 버튼 */}
                <div className="flex gap-2 pt-1">
                  {aggregatedData.cluster_triggered && aggregatedData.proposal_id && (
                    <a
                      href={`${API_BASE}/api/proposal/${aggregatedData.proposal_id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="flex-1 text-center px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors"
                    >
                      공식 제안서 보기
                    </a>
                  )}
                  <Link
                    href={`/cluster/${aggregatedData.cluster_id}`}
                    className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 border border-blue-300 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-50 transition-colors"
                  >
                    <Users size={14} />
                    집계 현황 보기
                  </Link>
                </div>
              </div>
            </>
          ) : (
            <>
              {/* 민원: 접수 완료 */}
              <div className="bg-gradient-to-r from-green-600 to-green-700 rounded-xl p-6 text-white">
                <div className="flex items-center gap-2 mb-1">
                  <CheckCircle size={20} />
                  <span className="font-semibold text-lg">민원이 접수되었습니다!</span>
                </div>
                <p className="text-green-200 text-sm">담당 기관에 전달됩니다</p>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-3">
                <h3 className="font-semibold text-gray-800">📋 접수 정보</h3>
                <div className="space-y-2">
                  {[
                    { label: '접수번호', value: aggregatedData.receipt_number, mono: true },
                    { label: '담당 기관', value: aggregatedData.responsible_dept },
                    { label: '처리 예정', value: `약 ${aggregatedData.expected_days}일 이내` },
                  ].map(r => (
                    <div key={r.label} className="flex justify-between items-center text-sm py-1.5 border-b border-gray-50 last:border-0">
                      <span className="text-gray-500">{r.label}</span>
                      <span className={`font-medium ${r.mono ? 'font-mono text-blue-700' : 'text-gray-800'}`}>{r.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* 제안서 다운로드 */}
          {aggregatedData.download_url && (
            <a
              href={`${API_BASE}${aggregatedData.download_url}`}
              download
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 transition-colors"
            >
              <Download size={18} />
              제안서 DOCX 다운로드
            </a>
          )}

          {/* 트렌딩 키워드 */}
          {aggregatedData.trending_keywords && aggregatedData.trending_keywords.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-gray-800">🔥 지금 핫한 키워드</h3>
                <Link href="/clusters" className="text-xs text-blue-600 hover:underline">전체 보기 →</Link>
              </div>
              <div className="space-y-2">
                {(() => {
                  const maxCount = aggregatedData.trending_keywords![0].total_count || 1
                  return aggregatedData.trending_keywords!.slice(0, 5).map((item, i) => (
                    <div key={item.keyword} className="flex items-center gap-2.5">
                      <span className="text-xs font-bold text-gray-400 w-4 flex-shrink-0">{i + 1}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-0.5">
                          {item.cluster_id ? (
                            <Link href={`/cluster/${item.cluster_id}`}
                              className="text-sm font-medium text-blue-700 hover:underline truncate">
                              {item.keyword}
                            </Link>
                          ) : (
                            <span className="text-sm font-medium text-gray-800 truncate">{item.keyword}</span>
                          )}
                          <span className="text-xs text-gray-400 ml-2 flex-shrink-0">{item.total_count}</span>
                        </div>
                        <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-blue-400 to-blue-600 rounded-full"
                            style={{ width: `${Math.round((item.total_count / maxCount) * 100)}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  ))
                })()}
              </div>
            </div>
          )}

          <button
            onClick={resetAll}
            className="w-full text-sm text-gray-400 hover:text-gray-600 py-2"
          >
            새 의견 제출하기
          </button>
        </div>
      )}
    </div>
  )
}
