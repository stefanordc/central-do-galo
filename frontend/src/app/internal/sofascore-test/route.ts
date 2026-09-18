export const dynamic = "force-dynamic";

export async function GET() {
  const url = "https://www.sofascore.com/api/v1/event/16881450/statistics";

  try {
    const response = await fetch(url, {
      cache: "no-store",
      headers: {
        "User-Agent": "Mozilla/5.0",
        Accept: "application/json, text/plain, */*",
        Referer: "https://www.sofascore.com/",
      },
    });

    const text = await response.text();
    let payload: unknown = null;

    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }

    return Response.json({
      status: response.status,
      ok: response.ok,
      contentType: response.headers.get("content-type"),
      keys:
        payload && typeof payload === "object"
          ? Object.keys(payload as Record<string, unknown>)
          : [],
      preview: text.slice(0, 300),
    });
  } catch (error) {
    return Response.json(
      { ok: false, error: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}
