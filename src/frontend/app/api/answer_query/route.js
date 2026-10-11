import { NextResponse } from 'next/server';

export async function POST(req) {
  const body = await req.json();
  const backendUrl = process.env.BACKEND_URL || 'http://backend:8000';

  const res = await fetch(`${backendUrl}/api/answer_query/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}