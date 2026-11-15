import { Navigate, Route, Routes } from "react-router-dom";
import ProjectDetailsPage from "./pages/ProjectDetailsPage";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import WorkspacesPage from "./pages/WorkspacesPage";
import WorkspaceDetailsPage from "./pages/WorkspaceDetailsPage";

import ProtectedRoute from "./components/layout/ProtectedRoute";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<DashboardPage />} />

        <Route path="/workspaces" element={<WorkspacesPage />} />

        <Route path="/workspaces/:slug" element={<WorkspaceDetailsPage />} />
        <Route path="/projects/:projectId" element={<ProjectDetailsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}