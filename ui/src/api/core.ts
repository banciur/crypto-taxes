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

type ApiErrorBody = {
  detail?: string;
};

export class ApiError extends Error {
  readonly path: string;
  readonly status: number;
  readonly detail: string;

  constructor({
    path,
    status,
    detail,
  }: {
    path: string;
    status: number;
    detail: string;
  }) {
    super(`Request failed for ${path}: ${status} : ${detail}`);
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

const parseApiErrorDetail = async (response: Response): Promise<string> => {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    const data = (await response.json().catch(() => undefined)) as unknown;
    if (isObjectOrArray(data)) {
      const camelizedData = camelcaseKeys(data, { deep: true }) as ApiErrorBody;
      if (typeof camelizedData.detail === "string" && camelizedData.detail) {
        return camelizedData.detail;
      }
    }
  }

  return (
    (await response.text().catch(() => "missing details")) || "missing details"
  );
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
    throw new ApiError({
      path,
      status: response.status,
      detail: await parseApiErrorDetail(response),
    });
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

export const mutateApi = async <T = void>(
  path: string,
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  payload: object,
): Promise<T | undefined> => {
  return doApiRequest<T>(path, {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: payload,
  });
};
