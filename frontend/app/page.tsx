'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import BrandLogo from '@/components/BrandLogo'
import ConversationBox from '@/components/ConversationBox'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

interface TrendingKeyword {
  keyword: string
  total_count: number
}

export default function Home() {
  const [trending, setTrending] = useState<TrendingKeyword[]>([])

  useEffect(() => {
    const load = () =>
      fetch(`${API_BASE}/api/clusters/trending-keywords`)
        .then(r => r.json())
        .then(d => setTrending(d.trending_keywords || []))
        .catch(() => {})
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [])

  const maxCount = trending[0]?.total_count || 1

  return (
    <main className="min-h-screen bg-gray-50">
      <nav className="sticky top-0 z-40 border-b border-gray-200 bg-white/80 backdrop-blur-sm">
        <div className="mx-auto max-w-6xl px-4 py-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <BrandLogo />
          <div className="flex items-center gap-3">
            <Link href="/complaints" className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors">
              민원 목록
            </Link>
            <Link href="/clusters" className="rounded-lg px-4 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 transition-colors">
              집계 현황
            </Link>
            <a href="#chat" className="rounded-lg bg-blue-600 px-6 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors">
              시작하기
            </a>
          </div>
        </div>
      </nav>

      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <section id="chat" className="grid gap-8 lg:grid-cols-[1fr_0.9fr]">
          {/* 좌측: 입력 박스 */}
          <div className="rounded-3xl border border-gray-200 bg-white p-8 shadow-lg">
            <div className="mb-8 pb-6 border-b border-gray-200">
              <p className="text-sm uppercase tracking-wider text-blue-600 font-semibold mb-2">즉시 시작</p>
              <h3 className="text-3xl font-bold text-gray-900">지금 바로 민원을 접수하세요</h3>
            </div>
            <ConversationBox />
          </div>

          {/* 우측: 안내 카드 */}
          <div className="space-y-6">
            <div className="rounded-2xl bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 p-6 shadow-md">
              <h4 className="text-lg font-bold text-blue-900 mb-3">뭐든 자유롭게 말씀하세요</h4>
              <ul className="space-y-2 text-sm text-blue-800">
                <li>• "○○ 제도가 불합리합니다" (민원)</li>
                <li>• "청년 주거 지원을 이렇게 바꾸면 어떨까요" (제안)</li>
                <li>• "○○법을 개정해야 합니다" (청원)</li>
                <li>• AI가 자동으로 분류하고 집계합니다</li>
              </ul>
            </div>

            <div className="rounded-2xl bg-gradient-to-br from-amber-50 to-yellow-50 border border-amber-200 p-6 shadow-md">
              <h4 className="text-lg font-bold text-amber-900 mb-3">🔗 함께할수록 강해집니다</h4>
              <p className="text-sm text-amber-800">
                같은 방향의 의견이 모일수록 집계 카운트가 올라가고,
                목표에 도달하면 AI가 공식 제안서를 자동 생성합니다.
              </p>
            </div>

            {/* 핫 키워드 TOP 5 */}
            <div className="rounded-2xl bg-white border border-gray-200 p-6 shadow-md">
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-bold text-gray-900">🔥 지금 핫한 키워드</h4>
                <Link href="/clusters" className="text-xs text-blue-600 hover:underline">전체 보기 →</Link>
              </div>
              {trending.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-4">아직 집계된 데이터가 없습니다</p>
              ) : (
                <div className="space-y-2.5">
                  {trending.map((item, i) => (
                    <div key={item.keyword} className="flex items-center gap-3">
                      <span className="text-xs font-bold text-gray-400 w-4 flex-shrink-0">{i + 1}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium text-gray-800 truncate">{item.keyword}</span>
                          <span className="text-xs text-gray-500 ml-2 flex-shrink-0">{item.total_count}</span>
                        </div>
                        <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-blue-400 to-blue-600"
                            style={{ width: `${Math.round((item.total_count / maxCount) * 100)}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  )
}
