import { useEffect, useState } from "react";

import type { JobSnapshot } from "../api/types";

export interface JobState extends JobSnapshot {
  status: JobSnapshot["status"] | "idle" | "timeout";
}

export interface UseJobOptions {
  fetchJob: (id: string) => Promise<JobSnapshot>;
  intervalMs?: number;
  timeoutMs?: number;
  maxIntervalMs?: number;
}

const INITIAL: JobState = { status: "idle", progress: 0, message: "", error: null };

/**
 * 轮询一个 job 直到 succeeded / failed / timeout。
 * 超时或请求异常都会停，绝不无限转圈（Review Focus 2）。
 */
export function useJob(jobId: string | null | undefined, options: UseJobOptions): JobState {
  const [state, setState] = useState<JobState>(INITIAL);

  const { fetchJob, intervalMs = 1000, timeoutMs = 10 * 60 * 1000, maxIntervalMs = 5000 } = options;

  useEffect(() => {
    if (!jobId) {
      setState(INITIAL);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const startedAt = Date.now();
    let delay = intervalMs;

    const tick = async () => {
      try {
        const snapshot = await fetchJob(jobId);
        if (cancelled) return;
        setState(snapshot as JobState);
        if (snapshot.status === "succeeded" || snapshot.status === "failed") return;
      } catch (error) {
        if (!cancelled) {
          setState({
            status: "failed",
            progress: 0,
            message: "",
            error: error instanceof Error ? error.message : String(error),
          });
        }
        return;
      }

      if (Date.now() - startedAt > timeoutMs) {
        if (!cancelled) {
          setState({ status: "timeout", progress: 0, message: "", error: "等待超时" });
        }
        return;
      }

      delay = Math.min(Math.round(delay * 1.5) || intervalMs, maxIntervalMs);
      timer = setTimeout(tick, delay);
    };

    void tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, fetchJob, intervalMs, timeoutMs, maxIntervalMs]);

  return state;
}
