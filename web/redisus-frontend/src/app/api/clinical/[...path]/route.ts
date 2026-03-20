import { NextRequest, NextResponse } from "next/server";

const UPSTREAM_BASE =
  process.env.CLINICAL_API_URL ??
  process.env.NEXT_PUBLIC_CLINICAL_API_URL ??
  "http://localhost:5000/api/v1";

function buildUpstreamUrl(pathParts: string[], search: string) {
  const normalizedBase = UPSTREAM_BASE.replace(/\/+$/, "");
  const normalizedPath = pathParts.map(encodeURIComponent).join("/");
  return `${normalizedBase}/${normalizedPath}${search}`;
}

async function proxy(request: NextRequest, pathParts: string[]) {
  const url = buildUpstreamUrl(pathParts, request.nextUrl.search);
  const headers = new Headers(request.headers);

  headers.delete("host");
  headers.delete("connection");
  headers.delete("content-length");

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  let upstream: Response;
  try {
    upstream = await fetch(url, init);
  } catch (error) {
    const detail = error instanceof Error ? error.message : "upstream unavailable";
    return NextResponse.json(
      { error: "clinical_api_unreachable", detail },
      { status: 502 }
    );
  }

  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("transfer-encoding");
  responseHeaders.delete("connection");

  const responseBody =
    upstream.status === 204 || upstream.status === 304
      ? null
      : await upstream.arrayBuffer();

  return new NextResponse(responseBody, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

export async function GET(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function POST(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxy(request, path);
}
