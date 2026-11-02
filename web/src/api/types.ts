export type JobStatus = "pending" | "running" | "succeeded" | "failed";

export interface JobSnapshot {
  status: JobStatus;
  progress: number;
  message: string;
  error?: string | null;
}

export interface Background {
  role?: string;
  current_work?: string;
  bottlenecks?: string;
  stack?: string;
  near_term_goals?: string;
  non_interests?: string;
}

export interface SettingsView {
  baseUrl: string;
  model: string;
  apiKey: string;
  apiKeyMasked: boolean;
  windowDays: number;
  background: Background;
  title: string;
  shareMinutes: number;
  wordsPerMinute: number;
  minPapers: number;
  maxPapers: number;
}

export interface Topic {
  id: number;
  key: string;
  label: string;
  keywords: string[];
  weight: number;
  enabled: boolean;
}

export interface Source {
  id: number;
  kind: "arxiv" | "rss" | "search";
  name: string;
  url: string;
  config: Record<string, unknown>;
  weight: number;
  enabled: boolean;
}

export interface PaperSummary {
  one_line?: string;
  core_problem?: string;
  technique?: string;
  results?: string;
  outlook?: string;
}

export interface PaperInIssue {
  id: string;
  title: string;
  url: string;
  topicKey: string;
  published?: string;
  oneLine: string;
  summary: PaperSummary;
  status: "ok" | "failed";
}

export interface NewsItem {
  title: string;
  source: string;
  oneLine: string;
  detail: string;
  url: string;
}

export interface IssueDetail {
  id: string;
  title: string;
  createdAt: string;
  status: string;
  targetWords: number;
  papers: PaperInIssue[];
  news: NewsItem[];
}

export interface IssueListItem {
  id: string;
  title: string;
  createdAt: string;
  windowDays: number;
  status: string;
  targetWords: number;
}

export interface DeepRead {
  why_it_matters?: string;
  background?: string;
  what_they_did?: string;
  why_it_works?: string;
  limits?: string;
  value_for_you?: string;
  verdict?: 1 | 2 | 3;
  jargon?: Array<[string, string]>;
  fulltext_status?: "full" | "abstract_only";
}

export interface ReproPlan {
  evidence?: { level?: string; note?: string; likelihood?: string; missing?: string[]; handoff_prompt?: string };
  estimate?: { token_range?: [number, number]; time_range_days?: [number, number] };
  planMd?: string;
}

export interface PaperDetail {
  id: string;
  title: string;
  url: string;
  abstract: string;
  fulltextStatus: "full" | "abstract_only";
  deepRead: DeepRead | null;
  reproPlan: ReproPlan | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}
