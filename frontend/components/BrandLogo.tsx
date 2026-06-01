'use client'

import Image from 'next/image'
import Link from 'next/link'

export default function BrandLogo() {
  return (
    <Link href="/" className="flex items-center gap-3">
      <Image
        src="/logo.jpg"
        alt="JUTAI 로고"
        width={52}
        height={52}
        className="rounded-xl"
        priority
      />
      <div>
        <p className="text-xs text-blue-600 font-semibold tracking-wider">AI 민원 제안 플랫폼</p>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">JUT_AI신문고</h1>
        <p className="text-xs text-gray-500 font-medium">정부 시스템 기반 스마트 접수</p>
      </div>
    </Link>
  )
}
