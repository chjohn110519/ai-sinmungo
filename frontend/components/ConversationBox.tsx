'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, Mic, MicOff, Download, CheckCircle, Circle, ChevronRight, FileText, Paperclip, X, Image as ImageIcon } from 'lucide-react'
import Link from 'next/link'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'
const STORAGE_KEY = 'complaint_sessions'

type Stage = 'idle' | 'questioning' | 'improving' | 'complete'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Ctx = Record<string, any>

interface QuestioningState {
  session_id: string
  classification: string
  responsible_dept: string
  confidence: number
  questions: string[]
  ctx?: Ctx
}

interface Improvement {
  id: number
  category: string
  suggestion: string
  impact: string
  requires_info?: string
}

interface ImprovingState {
  session_id: string
  classification: string
  draft_proposal: {
    title: string
    background: string
    core_requests: string
    expected_effects: string
    responsible_dept: string
    related_laws: string[]
  }
  improvements: Improvement[]
  related_laws: Array<{ title: string; snippet?: string }>
  ctx?: Ctx
}

interface CompleteState {
  session_id: string
  classification: string
  final_proposal: {
    title: string
    background: string
    core_requests: string
    expected_effects: string
    responsible_dept: string
    related_laws: string[]
  }
  review: {
    validity_score: number
    strengths: string[]
    weaknesses: string[]
  }
  analysis: {
    feasibility_score: number
    pass_probability: number
    expected_duration_days: number
  }
  download_url: string
}

interface AttachmentPreview {
  id: string
  name: string
  type: string
  size: number
  uploading: boolean
  error?: string
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

export default function ConversationBox() {
  const [stage, setStage] = useState<Stage>('idle')
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Stage-specific state
  const [questioningData, setQuestioningData] = useState<QuestioningState | null>(null)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [improvingData, setImprovingData] = useState<ImprovingState | null>(null)
  const [acceptedIds, setAcceptedIds] = useState<Set<number>>(new Set())
  const [userNote, setUserNote] = useState('')
  const [completeData, setCompleteData] = useState<CompleteState | null>(null)

  // Attachments
  const [attachments, setAttachments] = useState<AttachmentPreview[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])

  const sessionId = questioningData?.session_id || improvingData?.session_id || completeData?.session_id || null

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
      setInput('')
      setAttachments([])
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '오류가 발생했습니다.')
    } finally {
      setIsLoading(false)
    }
  }

  // ── TURN 2: 질문 답변 전송 ─────────────────────────────────────────────────
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
      setAcceptedIds(new Set(data.improvements.map(i => i.id)))
      setUserNote('')
      setStage('improving')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '오류가 발생했습니다.')
    } finally {
      setIsLoading(false)
    }
  }

  // ── TURN 3: 개선안 수락 후 최종 완성 ──────────────────────────────────────
  async function handleFinalize() {
    if (!improvingData) return
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/conversation/finalize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: improvingData.session_id,
          accepted_improvement_ids: Array.from(acceptedIds),
          user_note: userNote,
          ctx: improvingData.ctx,   // 서버리스용: 컨텍스트 전달
        }),
      })
      if (!res.ok) throw new Error(await res.text())
      const data: CompleteState = await res.json()
      setCompleteData(data)
      setStage('complete')
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
      const idx = attachments.length
      try {
        const formData = new FormData()
        formData.append('file', file)
        if (sessionId) formData.append('session_id', sessionId)
        const res = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: formData })
        if (!res.ok) throw new Error(await res.text())
        const data = await res.json()
        setAttachments(prev => prev.map((a, i) =>
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
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      audioChunksRef.current = []
      mr.ondataavailable = e => audioChunksRef.current.push(e.data)
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        const formData = new FormData()
        formData.append('audio', blob, 'recording.webm')
        try {
          const res = await fetch(`${API_BASE}/api/voice/transcribe`, { method: 'POST', body: formData })
          if (res.ok) {
            const data = await res.json()
            setInput(prev => prev + (prev ? ' ' : '') + data.text)
          }
        } catch {}
      }
      mr.start()
      mediaRecorderRef.current = mr
      setIsRecording(true)
    } catch {
      setError('마이크 접근 권한이 필요합니다.')
    }
  }

  function resetAll() {
    setStage('idle')
    setInput('')
    setQuestioningData(null)
    setImprovingData(null)
    setCompleteData(null)
    setAnswers({})
    setAcceptedIds(new Set())
    setUserNote('')
    setAttachments([])
    setError(null)
  }

  const categoryColors: Record<string, string> = {
    '법적근거강화': 'bg-blue-100 text-blue-800',
    '데이터보완': 'bg-green-100 text-green-800',
    '대상확장': 'bg-purple-100 text-purple-800',
    '제도적맥락': 'bg-orange-100 text-orange-800',
    '표현개선': 'bg-pink-100 text-pink-800',
  }

  // ── Stage 진행 표시 ────────────────────────────────────────────────────────
  const stages = [
    { key: 'idle', label: '민원 작성' },
    { key: 'questioning', label: 'AI 질문' },
    { key: 'improving', label: '개선안 검토' },
    { key: 'complete', label: '제안서 완성' },
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
          <h2 className="text-lg font-semibold text-gray-800">민원·제안·청원을 작성해주세요</h2>
          <p className="text-sm text-gray-500">
            불편하신 내용을 자유롭게 작성하시면 AI가 공식 제안서로 완성해드립니다.
          </p>
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
              className={`p-2 rounded-lg border ${isRecording ? 'bg-red-500 text-white border-red-500 animate-pulse' : 'text-gray-500 hover:bg-gray-100 border-gray-200'}`}
              title={isRecording ? '녹음 중지' : '음성 입력'}
            >
              {isRecording ? <MicOff size={18} /> : <Mic size={18} />}
            </button>
            <div className="flex-1" />
            <button
              onClick={handleStart}
              disabled={isLoading || (!input.trim() && attachments.filter(a => a.id).length === 0)}
              className="flex items-center gap-2 px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? '분류 중…' : '민원 접수'}
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

          <div>
            <h2 className="text-base font-semibold text-gray-800 mb-1">
              제안서 품질을 높이기 위해 몇 가지 여쭤볼게요
            </h2>
            <p className="text-sm text-gray-500">모든 질문에 답변하지 않아도 됩니다.</p>
          </div>

          <div className="space-y-4">
            {questioningData.questions.map((q, i) => (
              <div key={i} className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">
                  Q{i + 1}. {q}
                </label>
                <textarea
                  value={answers[i] || ''}
                  onChange={e => setAnswers(prev => ({ ...prev, [i]: e.target.value }))}
                  placeholder="답변을 입력하세요 (선택)"
                  rows={2}
                  className="w-full border border-gray-300 rounded-lg p-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
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

      {/* ── STAGE: improving ──────────────────────────────────────────────────── */}
      {stage === 'improving' && improvingData && (
        <div className="space-y-4">
          {/* Draft proposal summary */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-3">
            <div className="flex items-start justify-between gap-2">
              <h2 className="text-base font-semibold text-gray-800">
                📄 {improvingData.draft_proposal.title}
              </h2>
              <span className={`flex-shrink-0 px-2 py-0.5 rounded text-xs font-medium ${
                improvingData.classification === '민원' ? 'bg-orange-100 text-orange-700' :
                improvingData.classification === '제안' ? 'bg-blue-100 text-blue-700' :
                'bg-purple-100 text-purple-700'
              }`}>{improvingData.classification}</span>
            </div>
            <p className="text-sm text-gray-600 line-clamp-3">{improvingData.draft_proposal.background}</p>
            {improvingData.draft_proposal.related_laws.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {improvingData.draft_proposal.related_laws.slice(0, 5).map((law, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full">{law}</span>
                ))}
              </div>
            )}
          </div>

          {/* Improvements */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-4">
            <div>
              <h3 className="text-base font-semibold text-gray-800">통과 확률을 높이는 개선안</h3>
              <p className="text-sm text-gray-500 mt-0.5">원하는 개선안을 선택하세요. 선택한 항목이 최종 제안서에 반영됩니다.</p>
            </div>

            <div className="space-y-3">
              {improvingData.improvements.map(imp => {
                const accepted = acceptedIds.has(imp.id)
                return (
                  <div
                    key={imp.id}
                    onClick={() => setAcceptedIds(prev => {
                      const next = new Set(prev)
                      if (next.has(imp.id)) next.delete(imp.id)
                      else next.add(imp.id)
                      return next
                    })}
                    className={`cursor-pointer rounded-lg border p-4 transition-all ${
                      accepted ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`mt-0.5 flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                        accepted ? 'border-blue-500 bg-blue-500' : 'border-gray-300'
                      }`}>
                        {accepted && <CheckCircle size={12} className="text-white" />}
                      </div>
                      <div className="flex-1 space-y-1.5">
                        <div className="flex items-center gap-2">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${categoryColors[imp.category] || 'bg-gray-100 text-gray-700'}`}>
                            {imp.category}
                          </span>
                        </div>
                        <p className="text-sm text-gray-800">{imp.suggestion}</p>
                        <p className="text-xs text-gray-500">💡 {imp.impact}</p>
                        {imp.requires_info && (
                          <p className="text-xs text-amber-600">⚠ 추가 정보 필요: {imp.requires_info}</p>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            <div className="space-y-1.5 pt-1">
              <label className="text-sm font-medium text-gray-700">추가 요청사항 (선택)</label>
              <textarea
                value={userNote}
                onChange={e => setUserNote(e.target.value)}
                placeholder="추가로 강조하고 싶은 내용을 입력하세요..."
                rows={2}
                className="w-full border border-gray-300 rounded-lg p-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-center justify-between pt-1">
              <button onClick={resetAll} className="text-sm text-gray-400 hover:text-gray-600">
                ← 처음으로
              </button>
              <button
                onClick={handleFinalize}
                disabled={isLoading}
                className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-50"
              >
                {isLoading ? '제안서 완성 중…' : '제안서 완성하기'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── STAGE: complete ───────────────────────────────────────────────────── */}
      {stage === 'complete' && completeData && (
        <div className="space-y-4">
          {/* Success header */}
          <div className="bg-gradient-to-r from-blue-600 to-blue-700 rounded-xl p-6 text-white">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle size={20} />
              <span className="font-semibold">제안서가 완성되었습니다!</span>
            </div>
            <h2 className="text-xl font-bold">{completeData.final_proposal.title}</h2>
            <p className="text-blue-200 text-sm mt-1">{completeData.final_proposal.responsible_dept}</p>
          </div>

          {/* Analysis metrics */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: '실현 가능성', value: `${Math.round(completeData.analysis.feasibility_score * 100)}%`, color: 'text-blue-600' },
              { label: '통과 예상 확률', value: `${Math.round(completeData.analysis.pass_probability * 100)}%`, color: 'text-green-600' },
              { label: '예상 처리 기간', value: `${completeData.analysis.expected_duration_days}일`, color: 'text-orange-600' },
            ].map(m => (
              <div key={m.label} className="bg-white rounded-xl border border-gray-200 p-4 text-center">
                <div className={`text-2xl font-bold ${m.color}`}>{m.value}</div>
                <div className="text-xs text-gray-500 mt-1">{m.label}</div>
              </div>
            ))}
          </div>

          {/* Final proposal */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-4">
            <h3 className="font-semibold text-gray-800">최종 제안서 내용</h3>
            {[
              { label: '제안 배경', content: completeData.final_proposal.background },
              { label: '주요 요청 사항', content: completeData.final_proposal.core_requests },
              { label: '기대 효과', content: completeData.final_proposal.expected_effects },
            ].map(section => (
              <div key={section.label}>
                <h4 className="text-sm font-semibold text-gray-600 mb-1">{section.label}</h4>
                <p className="text-sm text-gray-700 whitespace-pre-line">{section.content}</p>
              </div>
            ))}
            {completeData.final_proposal.related_laws.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-gray-600 mb-1.5">관련 법령</h4>
                <div className="flex flex-wrap gap-1.5">
                  {completeData.final_proposal.related_laws.map((law, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full border border-blue-200">{law}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Review */}
          {completeData.review && (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-gray-800">AI 검토 의견</h3>
                <span className="text-sm font-bold text-blue-600">
                  타당성 {Math.round(completeData.review.validity_score * 100)}점
                </span>
              </div>
              {completeData.review.strengths?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-green-700 mb-1">강점</p>
                  <ul className="text-sm text-gray-700 space-y-0.5">
                    {completeData.review.strengths.map((s, i) => <li key={i}>✓ {s}</li>)}
                  </ul>
                </div>
              )}
              {completeData.review.weaknesses?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-amber-700 mb-1">보완점</p>
                  <ul className="text-sm text-gray-700 space-y-0.5">
                    {completeData.review.weaknesses.map((w, i) => <li key={i}>△ {w}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-3">
            <a
              href={`${API_BASE}${completeData.download_url}`}
              download
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 transition-colors"
            >
              <Download size={18} />
              DOCX 다운로드
            </a>
            {completeData.session_id && (
              <Link
                href={`/result/${completeData.session_id}`}
                className="flex items-center gap-2 px-4 py-3 bg-white text-blue-600 border border-blue-300 rounded-xl font-semibold hover:bg-blue-50 transition-colors"
              >
                상세 결과 보기
              </Link>
            )}
          </div>

          <button
            onClick={resetAll}
            className="w-full text-sm text-gray-400 hover:text-gray-600 py-2"
          >
            새 민원 작성하기
          </button>
        </div>
      )}
    </div>
  )
}
