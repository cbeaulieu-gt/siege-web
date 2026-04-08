import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import RequireAuth from "./components/RequireAuth";
import SiegeLayout from "./components/SiegeLayout";
import LoginPage from "./pages/LoginPage";
import MembersPage from "./pages/MembersPage";
import MemberDetailPage from "./pages/MemberDetailPage";
import SiegesPage from "./pages/SiegesPage";
import SiegeCreatePage from "./pages/SiegeCreatePage";
import SiegeSettingsPage from "./pages/SiegeSettingsPage";
import BoardPage from "./pages/BoardPage";
import PostsPage from "./pages/PostsPage";
import SiegeMembersPage from "./pages/SiegeMembersPage";
import ComparisonPage from "./pages/ComparisonPage";
import PostPrioritiesPage from "./pages/PostPrioritiesPage";
import SystemPage from "./pages/SystemPage";

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/sieges" replace />} />
        <Route path="/members" element={<MembersPage />} />
        <Route path="/members/new" element={<MemberDetailPage />} />
        <Route path="/members/:id" element={<MemberDetailPage />} />
        <Route path="/sieges" element={<SiegesPage />} />
        <Route path="/sieges/new" element={<SiegeCreatePage />} />
        <Route path="/sieges/:id" element={<SiegeLayout />}>
          <Route index element={<SiegeSettingsPage />} />
          <Route path="board" element={<BoardPage />} />
          <Route path="posts" element={<PostsPage />} />
          <Route path="members" element={<SiegeMembersPage />} />
          <Route path="compare" element={<ComparisonPage />} />
        </Route>
        <Route path="/post-priorities" element={<PostPrioritiesPage />} />
        <Route path="/system" element={<SystemPage />} />
      </Route>
    </Routes>
  );
}

export default App;
