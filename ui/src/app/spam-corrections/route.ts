import { NextResponse } from "next/server";

import { buildApiUrl } from "@/api/events";

const proxySpamCorrectionRequest = async (request: Request) => {
  const requestBody = await request.text();
  const response = await fetch(buildApiUrl("/spam-corrections"), {
    method: request.method,
    headers: {
      "Content-Type":
        request.headers.get("content-type") ?? "application/json",
    },
    body: requestBody,
    cache: "no-store",
  });

  const responseBody = await response.text();
  if (responseBody.length === 0) {
    return new NextResponse(null, { status: response.status });
  }

  return new NextResponse(responseBody, {
    status: response.status,
    headers: {
      "Content-Type":
        response.headers.get("content-type") ?? "text/plain; charset=utf-8",
    },
  });
};

export const POST = proxySpamCorrectionRequest;
export const DELETE = proxySpamCorrectionRequest;
