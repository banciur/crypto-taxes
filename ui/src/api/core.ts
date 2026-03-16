import camelcaseKeys from "camelcase-keys";
import decamelizeKeys from "decamelize-keys";

const DEFAULT_APP_ORIGIN = "http://localhost:3000";
const APP_ORIGIN = process.env.NEXT_PUBLIC_APP_ORIGIN ?? DEFAULT_APP_ORIGIN;
const API_PROXY_PREFIX = "/api/crypto-taxes";

// This file is messy, but for now it does it's job. Interfaces of mutateApi and doApiRequest could be improved around
// passing body, headers etc

type ApiRequestInit = Omit<RequestInit, "body"> & {
  body?: unknown;
};

export class ApiError extends Error {
  path: string;
  status: number;
  detail: string;

  constructor(path: string, status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.path = path;
    this.status = status;
    this.detail = detail;
  }
}

const resolveApiUrl = (path: string) => {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const proxyPath = `${API_PROXY_PREFIX}${normalizedPath}`;
  if (typeof window !== "undefined") {
    return proxyPath;
  }
  return new URL(proxyPath, APP_ORIGIN).toString();
};

const isObjectOrArray = (
  value: unknown,
): value is Record<string, unknown> | readonly unknown[] =>
  typeof value === "object" && value !== null;

const apiErrorDetail = (bodyText: string) => {
  if (bodyText.length === 0) {
    return "missing details";
  }

  try {
    const data = JSON.parse(bodyText) as unknown;
    if (
      typeof data === "object" &&
      data !== null &&
      "detail" in data &&
      typeof data.detail === "string"
    ) {
      return data.detail;
    }
  } catch {}

  return bodyText;
};

export const getApiErrorMessage = (error: unknown) => {
  if (error instanceof ApiError) {
    return error.detail;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Unknown error";
};

export const doApiRequest = async <T>(
  path: string,
  init?: ApiRequestInit,
): Promise<T | undefined> => {
  const body =
    init?.body === undefined
      ? undefined
      : JSON.stringify(
          decamelizeKeys(
            init.body as Record<string, unknown> | readonly unknown[],
            { deep: true },
          ),
        );
  const response = await fetch(resolveApiUrl(path), {
    cache: "no-store",
    ...init,
    body,
  });

  if (!response.ok) {
    const bodyText = await response.text().catch(() => "");
    throw new ApiError(path, response.status, apiErrorDetail(bodyText));
  }

  if (response.status === 204) {
    return undefined;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined;
  }

  const data = (await response.json()) as unknown;
  if (!isObjectOrArray(data)) {
    return data as T;
  }

  return camelcaseKeys(data, { deep: true }) as T;
};

export const getFromApi = async <T>(path: string): Promise<T> => {
  return (await doApiRequest<T>(path)) as T;
};

export const mutateApi = async (
  path: string,
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  payload: object,
): Promise<void> => {
  await doApiRequest(path, {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: payload,
  });
};
