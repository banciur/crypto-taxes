import { getFromApi } from "@/api/core";
import type { SystemState } from "@/types/systemState";

export const getSystemState = async (): Promise<SystemState> =>
  getFromApi<SystemState>("/system-state");
