import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import Gauge from "./Gauge";

describe("Gauge", () => {
  test.each([
    [1, "了解"],
    [2, "关注"],
    [3, "深入"],
  ])("第 %i 档读作「%s」", (level, label) => {
    render(<Gauge level={level as 1 | 2 | 3} />);
    expect(screen.getByRole("img", { name: `阅读深度：${label}` })).toBeInTheDocument();
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
