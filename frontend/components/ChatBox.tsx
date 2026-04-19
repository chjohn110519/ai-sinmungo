'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import { Send, Mic, MicOff, ExternalLink, Paperclip, X, FileText, Image as ImageIcon } from 'lucide-react'
import Link from 'next/link'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

interface PipelineStage {
  stage: number
  label: string
  status: 'pending' | 'running' | 'done' | 'error'
  data?: Record<string, unknown>
}

interface AttachmentPreview {
  id: string          // attachment_id from server (empty before upload)
  name: string
  type: string
  size: number
  uploading: boolean
  error?: string
}

const STAGE_LABELS = ['민원 분류', '문제 구조화', '법령 검색', '제안서 생성', '타당성 검토', '시각화 분석']
const STORAGE_KEY = 'complaint_sessions'
const HISTORY_KEY_PREFIX = 'chat_session_'

function fileIcon(type: string) {
  if (type.startsWith('image/')) return <ImageIcon size={14} />
  return <FileText size={14} />
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

export default function ChatBox() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [stages, setStages] = useState<PipelineStage[]>([])
  const [attachments, setAttachments] = useState<AttachmentPreview[]>([])
  const [historyRestored, setHistoryRestored] = useState(false)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 메시지 추가 시 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 마운트 시 localStorage에서 마지막 세션 복원
  useEffect(() => {
    const storedSessions = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') as string[]
    if (storedSessions.length === 0) { setHistoryRestored(true); return }

    const lastSessionId = storedSessions[storedSessions.length - 1]
    fetch(`/api/session/${lastSessionId}/messages`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (!data || data.messages.length === 0) return
        const restored: Message[] = data.messages
          .filter((m: { role: string }) => m.role === 'user' || m.role === 'assistant')
          .map((m: { message_id: string; role: string; content: string; created_at: string }) => ({
            id: m.message_id,
            role: m.role as 'user' | 'assistant',
            content: m.content,
            timestamp: new Date(m.created_at),
          }))
        if (restored.length > 0) {
          setMessages(restored)
          setSessionId(lastSessionId)
        }
      })
      .catch(() => {})
      .finally(() => setHistoryRestored(true))
  }, [])

  // 세션 ID를 localStorage에 저장
  const persistSession = useCallback((sid: string) => {
    const stored: string[] = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    if (!stored.includes(sid)) {
      stored.push(sid)
      localStorage.setItem(STORAGE_KEY, JSON.stringify(stored.slice(-50)))
    }
  }, [])

  const appendMessage = useCallback((msg: Message) => {
    setMessages((prev) => [...prev, msg])
  }, [])

  // 파일 업로드
  const uploadFile = useCallback(async (file: File, sid: string): Promise<string | null> => {
    const form = new FormData()
    form.append('file', file)
    form.append('session_id', sid)
    const r = await fetch('/api/upload', { method: 'POST', body: form })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      throw new Error(err.detail || '업로드 실패')
    }
    const data = await r.json()
    return data.attachment_id as string
  }, [])

  const handleFileSelect = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return
    const sid = sessionId || crypto.randomUUID()
    if (!sessionId) setSessionId(sid)

    const newAtts: AttachmentPreview[] = Array.from(files).map((f) => ({
      id: '',
      name: f.name,
      type: f.type || 'application/octet-stream',
      size: f.size,
      uploading: true,
    }))
    setAttachments((prev) => [...prev, ...newAtts])

    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      const idx = attachments.length + i
      try {
        const attId = await uploadFile(file, sid)
        setAttachments((prev) =>
          prev.map((a, j) => j === idx ? { ...a, id: attId || '', uploading: false } : a)
        )
      } catch (e) {
        setAttachments((prev) =>
          prev.map((a, j) => j === idx ? { ...a, uploading: false, error: (e as Error).message } : a)
        )
      }
    }
  }, [sessionId, attachments.length, uploadFile])

  const removeAttachment = (idx: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== idx))
  }

  const processWithSSE = useCallback(
    async (text: string) => {
      if (!text.trim()) return
      setIsLoading(true)
      setStages(STAGE_LABELS.map((label, i) => ({ stage: i + 1, label, status: 'pending' })))

      appendMessage({ id: Date.now().toString(), role: 'user', content: text, timestamp: new Date() })

      const sid = sessionId || ''
      const uploadedIds = attachments.filter((a) => a.id && !a.uploading).map((a) => a.id)
      const encoded = encodeURIComponent(text)
      const sidParam = sid ? `&session_id=${sid}` : ''
      const attParam = uploadedIds.length ? `&attachment_ids=${uploadedIds.join(',')}` : ''
      const url = `/api/chat/stream?message=${encoded}${sidParam}${attParam}`
      const eventSource = new EventSource(url)

      eventSource.onmessage = (e) => {
        try {
          const payload = JSON.parse(e.data)

          if (typeof payload.stage === 'number') {
            setStages((prev) =>
              prev.map((s) =>
                s.stage === payload.stage
                  ? { ...s, status: payload.status, data: payload.data, label: payload.label }
                  : s,
              ),
            )
          }

          if (payload.stage === 'complete') {
            eventSource.close()
            setIsLoading(false)
            setAttachments([])
            const r = payload.result
            if (r) {
              const newSid = r.session_id
              setSessionId(newSid)
              persistSession(newSid)
              const content = buildResultText(r.routing_result, r.structured_problem, r.related_laws, r.policy_proposal, r.proposal_review, r.visual_analysis)
              appendMessage({ id: (Date.now() + 1).toString(), role: 'assistant', content, timestamp: new Date() })
              setStages([])
            }
          }

          if (payload.stage === 'error') {
            eventSource.close()
            setIsLoading(false)
            appendMessage({ id: (Date.now() + 1).toString(), role: 'assistant', content: `처리 중 오류: ${payload.message}`, timestamp: new Date() })
            setStages([])
          }
        } catch { /* JSON 파싱 오류 무시 */ }
      }

      eventSource.onerror = () => {
        eventSource.close()
        setIsLoading(false)
        setStages([])
      }
    },
    [sessionId, appendMessage, attachments, persistSession],
  )

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (isLoading || !input.trim()) return
    const text = input
    setInput('')
    await processWithSSE(text)
  }

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      audioChunksRef.current = []
      const recorder = new MediaRecorder(stream)
      mediaRecorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data)
      }

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        const form = new FormData()
        form.append('audio', blob, 'recording.webm')
        setIsLoading(true)
        try {
          const res = await fetch('/api/voice/transcribe', { method: 'POST', body: form })
          const data = await res.json()
          const transcript = data.transcript || ''
          if (transcript) await processWithSSE(transcript)
          else {
            appendMessage({ id: Date.now().toString(), role: 'assistant', content: '음성을 인식하지 못했습니다. 다시 시도해 주세요.', timestamp: new Date() })
          }
        } catch {
          appendMessage({ id: Date.now().toString(), role: 'assistant', content: '음성 인식 중 오류가 발생했습니다.', timestamp: new Date() })
        } finally {
          setIsLoading(false)
        }
      }

      recorder.start()
      setIsRecording(true)
    } catch {
      alert('마이크 접근 권한이 필요합니다.')
    }
  }, [processWithSSE, appendMessage])

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop()
    setIsRecording(false)
  }, [])

  const clearHistory = useCallback(() => {
    if (!confirm('현재 대화 내용을 삭제하고 새로 시작할까요?')) return
    setMessages([])
    setSessionId(null)
    setAttachments([])
    setStages([])
  }, [])

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-50 to-white p-5 shadow-md">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.24em] text-blue-600 font-semibold">JUT_AI신문고 채팅</p>
            <h3 className="mt-2 text-xl font-bold text-gray-900">자연어로 민원·제안을 입력하세요.</h3>
            <p className="mt-2 text-sm text-gray-600">텍스트·음성·파일로 빠르게 접수합니다.</p>
          </div>
          <div className="flex gap-2 flex-wrap">
            {/* 마이크 */}
            <button
              type="button"
              onClick={isRecording ? stopRecording : startRecording}
              disabled={isLoading && !isRecording}
              className={`inline-flex cursor-pointer items-center gap-2 rounded-full border px-4 py-2 text-sm text-white transition shadow-md ${
                isRecording
                  ? 'border-red-500 bg-red-500 hover:bg-red-600 animate-pulse'
                  : 'border-blue-300 bg-blue-500 hover:bg-blue-600 shadow-blue-500/20'
              } disabled:opacity-50`}
            >
              {isRecording ? <MicOff size={18} /> : <Mic size={18} />}
              {isRecording ? '녹음 중지' : '음성 녹음'}
            </button>
            {/* 파일 첨부 */}
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-gray-300 bg-white hover:bg-gray-50 px-4 py-2 text-sm text-gray-600 transition shadow-sm">
              <Paperclip size={16} />
              파일 첨부
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.doc,.txt,image/*"
                className="hidden"
                disabled={isLoading}
                onChange={(e) => handleFileSelect(e.target.files)}
              />
            </label>
            {/* 새 대화 */}
            {messages.length > 0 && (
              <button
                type="button"
                onClick={clearHistory}
                className="inline-flex items-center gap-1 rounded-full border border-gray-300 bg-white hover:bg-gray-50 px-3 py-2 text-xs text-gray-500 transition"
              >
                새 대화
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 첨부파일 미리보기 */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {attachments.map((att, idx) => (
            <div
              key={idx}
              className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs ${
                att.error
                  ? 'border-red-200 bg-red-50 text-red-600'
                  : att.uploading
                  ? 'border-blue-200 bg-blue-50 text-blue-600 animate-pulse'
                  : 'border-gray-200 bg-gray-50 text-gray-600'
              }`}
            >
              {fileIcon(att.type)}
              <span className="max-w-[120px] truncate">{att.name}</span>
              <span className="text-gray-400">{formatBytes(att.size)}</span>
              {att.uploading && <span>업로드 중…</span>}
              {att.error && <span>오류</span>}
              {!att.uploading && (
                <button onClick={() => removeAttachment(idx)} className="text-gray-400 hover:text-red-500">
                  <X size={12} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 파이프라인 진행 표시 */}
      {stages.length > 0 && (
        <div className="rounded-xl border border-blue-100 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold text-gray-500 mb-3 uppercase tracking-wider">처리 단계</p>
          <div className="space-y-2">
            {stages.map((s) => (
              <div key={s.stage} className="flex items-center gap-3">
                <div className={`h-2 w-2 rounded-full flex-shrink-0 ${
                  s.status === 'done' ? 'bg-emerald-500'
                  : s.status === 'running' ? 'bg-blue-500 animate-pulse'
                  : s.status === 'error' ? 'bg-red-500'
                  : 'bg-gray-300'
                }`} />
                <span className={`text-sm ${
                  s.status === 'done' ? 'text-emerald-700'
                  : s.status === 'running' ? 'text-blue-700 font-medium'
                  : 'text-gray-400'
                }`}>
                  {s.status === 'done' ? '✓ ' : ''}{s.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 메시지 영역 */}
      <div className="h-[420px] overflow-y-auto rounded-2xl border border-gray-200 bg-white p-5 shadow-inner">
        {!historyRestored ? (
          <div className="flex h-full items-center justify-center text-gray-400">
            <div className="h-6 w-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : messages.length === 0 ? (
          <div className="flex h-full items-center justify-center text-gray-400">
            <div className="text-center">
              <p className="text-lg font-semibold text-gray-600 mb-2">민원이나 제안을 입력해주세요</p>
              <p className="text-sm text-gray-500">텍스트, 음성, 또는 파일을 첨부해 접수하세요</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`rounded-2xl p-4 shadow-sm ${
                  message.role === 'user'
                    ? 'ml-auto max-w-xs bg-blue-500 text-white border border-blue-600'
                    : 'max-w-sm bg-gray-100 text-gray-900 border border-gray-200'
                }`}
              >
                <div className={`text-xs font-semibold tracking-wider mb-1 ${
                  message.role === 'user' ? 'text-blue-100' : 'text-gray-500'
                }`}>
                  {message.role === 'user' ? '당신' : '✓ AI 분석 결과'}
                </div>
                <p className="text-sm leading-6 whitespace-pre-wrap">{message.content}</p>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
        {isLoading && stages.length === 0 && (
          <div className="mt-4 flex items-center justify-center gap-2 text-blue-600">
            <div className="h-2 w-2 rounded-full bg-blue-600 animate-bounce" style={{ animationDelay: '0ms' }} />
            <div className="h-2 w-2 rounded-full bg-blue-600 animate-bounce" style={{ animationDelay: '150ms' }} />
            <div className="h-2 w-2 rounded-full bg-blue-600 animate-bounce" style={{ animationDelay: '300ms' }} />
            <span className="text-sm font-medium ml-2">처리 중입니다…</span>
          </div>
        )}
      </div>

      {/* 결과 링크 */}
      {sessionId && !isLoading && (
        <div className="flex justify-end gap-2 flex-wrap">
          <Link
            href={`/status/${sessionId}`}
            className="inline-flex items-center gap-2 rounded-full border border-gray-300 bg-white hover:bg-gray-50 px-4 py-2 text-sm font-semibold text-gray-700 transition"
          >
            <ExternalLink size={15} />
            처리 현황 보기
          </Link>
          <Link
            href={`/result/${sessionId}`}
            className="inline-flex items-center gap-2 rounded-full bg-emerald-500 hover:bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition shadow-md"
          >
            <ExternalLink size={15} />
            결과 상세 보기
          </Link>
        </div>
      )}

      {/* 입력 폼 */}
      <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={attachments.length > 0 ? `파일 ${attachments.length}개 첨부됨 — 내용을 입력하세요…` : '민원이나 제안을 입력하세요...'}
          className="flex-1 rounded-full border border-gray-300 bg-white px-4 py-3 text-gray-900 placeholder-gray-500 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 shadow-sm"
          disabled={isLoading}
        />
        <button
          type="submit"
          className="inline-flex items-center justify-center rounded-full bg-blue-600 hover:bg-blue-700 px-6 py-3 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-50 shadow-lg shadow-blue-600/20"
          disabled={isLoading || (!input.trim() && attachments.filter((a) => a.id).length === 0)}
        >
          <Send size={18} className="mr-2" />
          제출
        </button>
      </form>
    </div>
  )
}

function buildResultText(
  routing: Record<string, unknown>,
  structured: Record<string, unknown> | null,
  laws: Array<Record<string, unknown>> | null,
  proposal: Record<string, unknown> | null,
  review: Record<string, unknown> | null,
  visual: Record<string, unknown> | null,
): string {
  const lines: string[] = []

  lines.push('📋 분류 결과')
  lines.push(`• 유형: ${routing?.classification}`)
  lines.push(`• 신뢰도: ${((routing?.confidence as number) * 100).toFixed(1)}%`)
  lines.push(`• 담당 부처: ${routing?.responsible_dept}`)
  lines.push('')

  if (structured) {
    lines.push('📌 구조화된 문제')
    lines.push(`• 원인: ${structured.cause}`)
    lines.push(`• 영향대상: ${structured.affected_subjects}`)
    lines.push('')
  }

  if (laws?.length) {
    lines.push('📚 관련 법령')
    ;(laws as Array<{ title: string; relevance: number; source?: string }>).forEach((law) => {
      const src = law.source ? ` [${law.source}]` : ''
      lines.push(`• ${law.title} (관련도: ${(law.relevance * 100).toFixed(0)}%)${src}`)
    })
    lines.push('')
  }

  if (proposal) {
    lines.push('💡 정책 제안서')
    lines.push(`• 제목: ${proposal.title}`)
    lines.push(`• 기대효과: ${proposal.expected_effects}`)
    lines.push('')
  }

  if (review) {
    lines.push('✅ 타당성 검토')
    lines.push(`• 점수: ${((review.validity_score as number) * 100).toFixed(0)}점`)
    const strengths = review.strengths as string[]
    if (strengths?.length) lines.push(`• 강점: ${strengths.slice(0, 2).join(', ')}`)
    const suggestions = review.revision_suggestions as string[]
    if (suggestions?.length) lines.push(`• 개선사항: ${suggestions[0]}`)
    lines.push('')
  }

  if (visual) {
    lines.push('📊 AI 분석')
    lines.push(`• 실현 가능성: ${((visual.feasibility_score as number) * 100).toFixed(0)}%`)
    lines.push(`• 통과 확률: ${((visual.pass_probability as number) * 100).toFixed(0)}%`)
    lines.push(`• 예상 기간: ${visual.expected_duration_days}일`)
  }

  return lines.join('\n').trim()
}
