export type SystemStateStatus = "NOT_RUN" | "RUNNING" | "COMPLETED" | "FAILED";

export type SystemStateStage =
  | "RAW_IMPORT"
  | "CORRECTIONS"
  | "WALLET_PROJECTION"
  | "ACQUISITION_DISPOSAL"
  | "TAX_COMPUTATION";

export type SystemStateError = {
  exceptionType: string;
  message: string;
  traceback: string | null;
};

export type SystemState = {
  status: SystemStateStatus;
  stage: SystemStateStage | null;
  startedAt: string | null;
  finishedAt: string | null;
  error: SystemStateError | null;
};
