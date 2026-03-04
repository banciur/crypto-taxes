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
    const details = await response.text().catch(() => "missing details");
    throw new Error(
      `Request failed for ${path}: ${response.status} : ${details || "missing details"}`,
    );
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
