import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";

import App from "./App";
import { ClientProvider } from "./api/context";

test("左栏列出六个入口", () => {
  render(
    <ClientProvider client={{} as never}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </ClientProvider>,
  );
  for (const label of ["本期文章", "生成新一期", "研究方向", "数据源", "历史文章", "设置"]) {
    expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
  }
});
