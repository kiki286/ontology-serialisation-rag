import { NextResponse } from 'next/server';

export async function POST() {
  try {
    const res = await fetch(process.env.BACKEND_URL + "/api/clear_rag_memory/", {
      method: "POST",
    });

    const data = await res.json();
    return Response.json(data);
  } catch (err) {
    console.error("Error calling backend clear:", err);
    return Response.json({ error: "Failed to reset memory" }, { status: 500 });
  }
}
