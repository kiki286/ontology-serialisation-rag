import { NextResponse } from 'next/server'

export async function GET() {
  const base = process.env.BACKEND_URL || 'http://backend:8000'
  try {
    const r = await fetch(`${base}/healthz`, { cache: 'no-store' })
    const data = await r.json()
    return NextResponse.json({ ok: true, target: base, backend: data })
  } catch (err) {
    return NextResponse.json(
      { ok: false, target: base, error: String(err) },
      { status: 502 }
    )
  }
}
