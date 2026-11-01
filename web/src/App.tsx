import { Route, Routes, useNavigate, useParams } from "react-router-dom";

import Rail from "./components/Rail";
import GeneratePage from "./pages/GeneratePage";
import HistoryPage from "./pages/HistoryPage";
import IssuePage from "./pages/IssuePage";
import ReaderPage from "./pages/ReaderPage";
import SetupPage from "./pages/SetupPage";
import SourcesPage from "./pages/SourcesPage";
import TopicsPage from "./pages/TopicsPage";

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
      </main>
    </div>
  );
}
