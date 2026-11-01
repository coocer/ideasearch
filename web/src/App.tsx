import { useEffect, useState, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";

import { useClient } from "./api/context";
import Rail from "./components/Rail";
import GeneratePage from "./pages/GeneratePage";
import HistoryPage from "./pages/HistoryPage";
import IssuePage from "./pages/IssuePage";
import ReaderPage from "./pages/ReaderPage";
import SetupPage from "./pages/SetupPage";
import SourcesPage from "./pages/SourcesPage";
import TopicsPage from "./pages/TopicsPage";

/** 没配 key 就把人送到设置页——首次进空库不能停在空列表（Review Focus 3）。 */
function OnboardingGate({ children }: { children: ReactNode }) {
  const client = useClient();
  const location = useLocation();
  const [state, setState] = useState<"loading" | "ready" | "needs">("loading");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const settings = await client.settings.get();
        if (!cancelled) setState(settings.apiKey ? "ready" : "needs");
      } catch {
        // 读不到配置时不挡路，交给页面自己报错
        if (!cancelled) setState("ready");
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [client, location.pathname]);

  if (state === "loading") return <p className="muted">正在读取配置…</p>;
  // 只在首页拦人：其它页面放行，避免保存 key 后被来回弹（评审 Critical）
  if (state === "needs" && location.pathname === "/") {
    return <Navigate to="/setup" replace />;
  }
  return <>{children}</>;
}

function GenerateRoute() {
  const navigate = useNavigate();
  return <GeneratePage onDone={(issueId) => navigate(`/issues/${issueId}`)} />;
}

function IssueRoute() {
  const { id } = useParams();
  return <IssuePage issueId={id} />;
}

function ReaderRoute() {
  const { paperId } = useParams();
  return <ReaderPage paperId={paperId} />;
}

export default function App() {
  return (
    <div className="app">
      <Rail />
      <main className="main">
        <OnboardingGate>
          <Routes>
            <Route path="/" element={<IssuePage />} />
            <Route path="/issues/:id" element={<IssueRoute />} />
            <Route path="/generate" element={<GenerateRoute />} />
            <Route path="/topics" element={<TopicsPage />} />
            <Route path="/sources" element={<SourcesPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/setup" element={<SetupPage />} />
            <Route path="/read/:paperId" element={<ReaderRoute />} />
          </Routes>
        </OnboardingGate>
      </main>
    </div>
  );
}
