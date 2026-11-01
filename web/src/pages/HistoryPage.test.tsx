import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, test } from "vitest";

import type { IssueListItem } from "../api/types";
import HistoryPage from "./HistoryPage";

const issue = (over: Partial<IssueListItem> = {}): IssueListItem => ({
  id: "i1",
  title: "推理系统的三个成本杠杆",
  createdAt: "2026-11-01T10:00:00",
  windowDays: 7,
  status: "succeeded",
  targetWords: 9000,
  ...over,
});

const renderPage = (items: IssueListItem[]) =>
  render(
    <MemoryRouter>
      <HistoryPage
        client={
          {
            issues: { list: async () => ({ items, total: items.length, page: 1, pageSize: items.length }) },
          } as never
        }
      />
    </MemoryRouter>,
  );

describe("HistoryPage", () => {
  test("空历史给出下一步动作", async () => {
    renderPage([]);
    expect(await screen.findByRole("link", { name: "去生成第一期" })).toHaveAttribute(
      "href",
      "/generate",
    );
  });

  test("列出历史并给出查看入口", async () => {
    renderPage([issue()]);
    expect(await screen.findByText(/推理系统的三个成本杠杆/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看" })).toHaveAttribute("href", "/issues/i1");
  });

  test("失败的一期标出来", async () => {
    renderPage([issue({ status: "failed" })]);
    expect(await screen.findByText(/失败/)).toBeInTheDocument();
  });
});
