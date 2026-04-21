'use client'

import Link from 'next/link'
import BrandLogo from '@/components/BrandLogo'
import ConversationBox from '@/components/ConversationBox'

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-white via-blue-50 to-gray-50">
      {/* 상단 네비게이션 */}
      <nav className="sticky top-0 z-40 border-b border-gray-200 bg-white/80 backdrop-blur-sm">
        <div className="mx-auto max-w-6xl px-4 py-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <BrandLogo />
          <div className="flex items-center gap-3">
            <Link
              href="/complaints"
              className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors"
            >
              민원 목록
            </Link>
            <Link
              href="/admin"
              className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors"
            >
              관리자
            </Link>
            <Link
              href="/clusters"
              className="rounded-lg px-4 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 transition-colors"
            >
              집계 현황
            </Link>
            <a
              href="#chat"
              className="rounded-lg bg-blue-600 px-6 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors shadow-lg shadow-blue-600/20"
            >
              시작하기
            </a>
          </div>
        </div>
      </nav>

      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        {/* 히어로 섹션 */}
        <div className="mb-16 rounded-3xl bg-gradient-to-br from-blue-600 to-blue-700 p-12 text-white shadow-xl shadow-blue-600/20">
          <div className="grid gap-8 lg:grid-cols-2 lg:items-center">
            <div>
              <p className="text-sm uppercase tracking-[0.32em] font-semibold text-blue-100 mb-4">
                단일 창구 시민 참여 플랫폼
              </p>
              <h2 className="text-5xl font-bold leading-tight tracking-tight sm:text-6xl mb-4">
                민원인지 청원인지<br />
                <span className="text-yellow-300">몰라도 됩니다</span>
              </h2>
              <p className="text-lg text-blue-100 mb-3 max-w-xl">
                하나의 창구에 자유롭게 말씀하시면 AI가 자동으로 분류하고,
                같은 목소리가 모일수록 더 설득력 있는 공식 제안서로 만들어드립니다.
              </p>
              <div className="flex flex-wrap gap-2 mb-8">
                {['민원', '제안', '청원'].map(t => (
                  <span key={t} className="px-3 py-1 rounded-full bg-white/15 text-white text-sm font-medium border border-white/30">
                    {t}
                  </span>
                ))}
                <span className="px-3 py-1 rounded-full bg-yellow-400/20 text-yellow-200 text-sm font-medium border border-yellow-400/30">
                  → AI가 자동 분류
                </span>
              </div>
              <a href="#chat" className="inline-block rounded-xl bg-white px-8 py-3 font-semibold text-blue-600 hover:bg-blue-50 transition-colors shadow-lg">
                지금 시작하기
              </a>
            </div>
            <div className="hidden lg:block">
              <div className="rounded-2xl bg-white/10 backdrop-blur p-8 border border-white/20">
                <div className="space-y-4">
                  <div className="rounded-xl bg-white/10 p-4 border border-white/20">
                    <p className="text-sm text-white font-semibold">같은 방향의 제안이 모이면</p>
                    <p className="text-2xl font-bold text-yellow-300">설득력이 높아집니다</p>
                  </div>
                  <div className="rounded-xl bg-white/10 p-4 border border-white/20">
                    <p className="text-sm text-white font-semibold">분류·청원·민원 구분 없이</p>
                    <p className="text-2xl font-bold text-yellow-300">하나의 창구로</p>
                  </div>
                  <div className="rounded-xl bg-white/10 p-4 border border-white/20">
                    <p className="text-sm text-white font-semibold">집계 후 AI가 자동으로</p>
                    <p className="text-2xl font-bold text-yellow-300">공식 문서를 생성합니다</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 기능 소개 */}
        <section className="mb-16">
          <div className="mb-12 text-center">
            <p className="text-blue-600 font-semibold uppercase tracking-wider mb-2">대표 기능</p>
            <h2 className="text-4xl font-bold text-gray-900">JUT_AI신문고의 핵심 기능</h2>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { icon: '🚪', title: '단일 창구', description: '민원·제안·청원을 구분 없이 하나의 창구에서 접수합니다.' },
              { icon: '🔗', title: '자동 집계', description: '같은 방향의 제안을 자동으로 묶어 목소리를 모읍니다.' },
              { icon: '📋', title: '공식 문서화', description: '집계된 제안을 법안 형식의 공식 제안서로 자동 생성합니다.' },
              { icon: '📊', title: '통과 예측', description: '누적 데이터 기반으로 통과 확률과 소요기간을 예측합니다.' },
            ].map((card) => (
              <div
                key={card.title}
                className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm hover:shadow-lg hover:border-blue-200 transition-all"
              >
                <div className="text-4xl mb-3">{card.icon}</div>
                <h3 className="text-lg font-bold text-gray-900 mb-2">{card.title}</h3>
                <p className="text-sm text-gray-600">{card.description}</p>
              </div>
            ))}
          </div>
        </section>

        {/* 실시간 접수 섹션 */}
        <section id="chat" className="mb-16 grid gap-8 lg:grid-cols-[1fr_0.9fr]">
          <div className="rounded-3xl border border-gray-200 bg-white p-8 shadow-lg">
            <div className="mb-8 pb-6 border-b border-gray-200">
              <p className="text-sm uppercase tracking-wider text-blue-600 font-semibold mb-2">
                즉시 시작
              </p>
              <h3 className="text-3xl font-bold text-gray-900">
                지금 바로 민원을 접수하세요
              </h3>
            </div>
            <ConversationBox />
          </div>

          <div className="space-y-6">
            {/* 안내 카드 */}
            <div className="rounded-2xl bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 p-6 shadow-md">
              <h4 className="text-lg font-bold text-blue-900 mb-3">뭐든 자유롭게 말씀하세요</h4>
              <ul className="space-y-2 text-sm text-blue-800">
                <li>• "○○ 제도가 불합리합니다" (민원)</li>
                <li>• "청년 주거 지원을 이렇게 바꾸면 어떨까요" (제안)</li>
                <li>• "○○법을 개정해야 합니다" (청원)</li>
                <li>• AI가 자동으로 분류하고 집계합니다</li>
              </ul>
            </div>

            {/* 집계 특징 카드 */}
            <div className="rounded-2xl bg-gradient-to-br from-amber-50 to-yellow-50 border border-amber-200 p-6 shadow-md">
              <h4 className="text-lg font-bold text-amber-900 mb-3">🔗 함께할수록 강해집니다</h4>
              <p className="text-sm text-amber-800">
                같은 방향의 의견이 모일수록 집계 카운트가 올라가고,
                목표에 도달하면 AI가 공식 제안서를 자동 생성합니다.
              </p>
            </div>

            {/* 신뢰도 카드 */}
            <div className="rounded-2xl bg-white border border-gray-200 p-6 shadow-md">
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-bold text-gray-900">신뢰도</h4>
                <span className="text-2xl font-bold text-blue-600">98%</span>
              </div>
              <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                <div className="h-full w-[98%] bg-gradient-to-r from-blue-500 to-blue-600"></div>
              </div>
            </div>
          </div>
        </section>

        {/* 프로세스 안내 */}
        <section className="mb-16">
          <div className="mb-12 text-center">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">작동 방식</h2>
            <p className="text-lg text-gray-600">집단 목소리가 공식 문서가 되는 과정</p>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { num: '1', title: '자유 입력', desc: '민원·제안·청원 구분 없이 자유롭게 입력' },
              { num: '2', title: 'AI 분류·집계', desc: 'AI가 자동 분류하고 같은 방향의 의견을 하나로 묶음' },
              { num: '3', title: '공식 문서화', desc: '집계가 쌓이면 AI가 법안 수준 제안서 자동 생성' },
              { num: '4', title: '통과 예측', desc: '누적 데이터 기반 통과 확률·소요기간 제공' },
            ].map((step) => (
              <div key={step.num} className="relative">
                <div className="rounded-2xl border border-blue-200 bg-blue-50 p-6 text-center">
                  <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-blue-600 text-white font-bold text-lg">
                    {step.num}
                  </div>
                  <h4 className="font-bold text-gray-900 mb-2">{step.title}</h4>
                  <p className="text-sm text-gray-600">{step.desc}</p>
                </div>
                {parseInt(step.num) < 4 && (
                  <div className="absolute right-0 top-1/2 translate-x-1/2 -translate-y-1/2 hidden lg:block">
                    <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* 하단 CTA */}
        <section className="rounded-3xl bg-gradient-to-r from-blue-600 to-blue-700 p-12 text-center text-white shadow-xl shadow-blue-600/20 mb-16">
          <h2 className="text-4xl font-bold mb-4">지금 바로 시작하세요</h2>
          <p className="text-lg text-blue-100 mb-8 max-w-2xl mx-auto">
            당신의 생각이 정책이 되는 경험을 해보세요.
            AI 신문고는 24시간 당신의 제안을 기다리고 있습니다.
          </p>
          <button className="rounded-xl bg-white px-8 py-4 font-bold text-blue-600 hover:bg-blue-50 transition-colors shadow-lg text-lg">
            민원 접수하기
          </button>
        </section>
      </div>

      {/* 하단 푸터 */}
      <footer className="border-t border-gray-200 bg-white py-8 text-center">
        <p className="text-gray-600">© 2026 JUT_AI신문고 | 정부 시스템 기반 스마트 민원 처리 플랫폼</p>
      </footer>
    </main>
  )
}
