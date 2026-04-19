'use client'

export default function BrandLogo() {
  return (
    <div className="flex items-center gap-4">
      {/* 정부 디자인 스타일 배지 */}
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 shadow-lg shadow-blue-300/40 relative">
        <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/20 to-transparent" />
        <div className="relative">
          <div className="text-xl font-bold text-white">신</div>
        </div>
      </div>
      <div>
        <p className="text-xs text-blue-600 font-semibold tracking-wider">AI 민원 제안 플랫폼</p>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">JUT_AI신문고</h1>
        <p className="text-xs text-gray-500 font-medium">정부 시스템 기반 스마트 접수</p>
      </div>
    </div>
  )
}
