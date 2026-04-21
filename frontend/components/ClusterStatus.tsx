'use client'

import Link from 'next/link'
import { Users, TrendingUp, CheckCircle } from 'lucide-react'

interface ClusterStatusProps {
  clusterId: string
  topic: string
  keywords: string[]
  classification: string
  count: number
  threshold: number
  triggered: boolean
  progressPercent: number
}

export default function ClusterStatus({
  clusterId,
  topic,
  keywords,
  classification,
  count,
  threshold,
  triggered,
  progressPercent,
}: ClusterStatusProps) {
  const remaining = Math.max(0, threshold - count)

  return (
    <div className={`rounded-xl border p-4 space-y-3 ${
      triggered
        ? 'border-green-300 bg-green-50'
        : 'border-blue-200 bg-blue-50'
    }`}>
      {/* 헤더 */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {triggered ? (
            <CheckCircle size={18} className="text-green-600 flex-shrink-0" />
          ) : (
            <Users size={18} className="text-blue-600 flex-shrink-0" />
          )}
          <span className={`text-sm font-semibold ${triggered ? 'text-green-800' : 'text-blue-800'}`}>
            {triggered ? '공식 문서가 생성되었습니다!' : `현재 ${count.toLocaleString()}명이 같은 주제로 제안 중`}
          </span>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
          classification === '제안' ? 'bg-blue-200 text-blue-800' : 'bg-purple-200 text-purple-800'
        }`}>
          {classification}
        </span>
      </div>

      {/* 주제 + 키워드 */}
      <div>
        <div className="flex items-center gap-1.5 mb-1.5">
          <TrendingUp size={13} className="text-gray-500" />
          <span className="text-xs text-gray-600 font-medium">주제: {topic}</span>
        </div>
        {keywords.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {keywords.slice(0, 6).map((kw) => (
              <span key={kw} className="text-xs px-1.5 py-0.5 bg-white border border-gray-200 text-gray-600 rounded">
                {kw}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 진행 바 */}
      {!triggered && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-gray-500">
            <span>{count.toLocaleString()}명 참여</span>
            <span>목표 {threshold.toLocaleString()}명 (공식 문서 생성 기준)</span>
          </div>
          <div className="w-full h-2 bg-white rounded-full overflow-hidden border border-blue-200">
            <div
              className="h-full bg-gradient-to-r from-blue-400 to-blue-600 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(progressPercent, 100)}%` }}
            />
          </div>
          <p className="text-xs text-blue-700">
            {remaining > 0
              ? `${remaining.toLocaleString()}명이 더 참여하면 AI가 공식 제안서를 자동 생성합니다`
              : '곧 공식 제안서가 생성됩니다!'}
          </p>
        </div>
      )}

      {/* 링크 */}
      <Link
        href={`/cluster/${clusterId}`}
        className={`block text-center text-xs font-medium py-1.5 rounded-lg transition-colors ${
          triggered
            ? 'bg-green-100 text-green-700 hover:bg-green-200'
            : 'bg-white text-blue-600 hover:bg-blue-100 border border-blue-200'
        }`}
      >
        집계 현황 자세히 보기 →
      </Link>
    </div>
  )
}
