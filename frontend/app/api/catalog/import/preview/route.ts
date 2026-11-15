import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 30;

const MAX_FILE_BYTES = 5 * 1024 * 1024;

export async function POST(request: Request) {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim().replace(/\/$/, "");

  if (!apiBaseUrl || !apiBaseUrl.startsWith("https://")) {
    return NextResponse.json(
      { detail: "CSV validation is temporarily unavailable because the API endpoint is not configured." },
      { status: 503 },
    );
  }

  let incoming: FormData;
  try {
    incoming = await request.formData();
  } catch {
    return NextResponse.json({ detail: "The uploaded form could not be read." }, { status: 400 });
  }

  const file = incoming.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ detail: "Choose a CSV file before validating." }, { status: 400 });
  }

  if (!file.name.toLowerCase().endsWith(".csv")) {
    return NextResponse.json({ detail: "Only CSV files are supported." }, { status: 415 });
  }

  if (file.size > MAX_FILE_BYTES) {
    return NextResponse.json({ detail: "The file exceeds the 5 MB limit." }, { status: 413 });
  }

  const outgoing = new FormData();
  outgoing.append("file", file, file.name);

  try {
    const upstream = await fetch(`${apiBaseUrl}/api/v1/catalog/import/preview`, {
      method: "POST",
      body: outgoing,
      cache: "no-store",
      signal: AbortSignal.timeout(25_000),
    });

    const payload = await upstream.json().catch(() => ({
      detail: "The validation service returned an unreadable response.",
    }));

    return NextResponse.json(payload, {
      status: upstream.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    const timedOut = error instanceof Error && error.name === "TimeoutError";
    return NextResponse.json(
      {
        detail: timedOut
          ? "The validation service took too long to respond. Please try again."
          : "The validation service could not be reached. Please try again shortly.",
      },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
