import { Routes, Route } from "react-router-dom";
import HomePage from "./pages/HomePage";
import MembersPage from "./pages/MembersPage";
import SiegesPage from "./pages/SiegesPage";
import BoardPage from "./pages/BoardPage";
import PostsPage from "./pages/PostsPage";
import SiegeMembersPage from "./pages/SiegeMembersPage";

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/members" element={<MembersPage />} />
      <Route path="/sieges" element={<SiegesPage />} />
      <Route path="/sieges/:id/board" element={<BoardPage />} />
      <Route path="/sieges/:id/posts" element={<PostsPage />} />
      <Route path="/sieges/:id/members" element={<SiegeMembersPage />} />
    </Routes>
  );
}

export default App;
