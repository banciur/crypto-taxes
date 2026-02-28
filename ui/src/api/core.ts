const DEFAULT_APP_ORIGIN = "http://localhost:3000";
const APP_ORIGIN = process.env.NEXT_PUBLIC_APP_ORIGIN ?? DEFAULT_APP_ORIGIN;
const API_PROXY_PREFIX = "/api/crypto-taxes";

const resolveApiUrl = (path: string) => {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const proxyPath = `${API_PROXY_PREFIX}${normalizedPath}`;
  if (typeof window !== "undefined") {
    return proxyPath;
  }
  return new URL(proxyPath, APP_ORIGIN).toString();
};

export const doApiRequest = async (
  path: string,
  init?: RequestInit,
): Promise<Response> => {
  const response = await fetch(resolveApiUrl(path), {
    cache: "no-store",
    ...init,
  });

  if (!response.ok) {
    const details = await response.text().catch(() => "missing details");
    throw new Error(
      `Request failed for ${path}: ${response.status} : ${details || "missing details"}`,
    );
  }

  return response;
};

export const getFromApi = async <T>(path: string): Promise<T> => {
  const response = await doApiRequest(path);
  return (await response.json()) as T;
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
    body: JSON.stringify(payload),
  });
};
