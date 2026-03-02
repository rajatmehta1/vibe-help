import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProjectProvider } from "@/contexts/ProjectContext";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Layout from "./components/layout/Layout";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Policies from "./pages/Policies";
import PolicyDetail from "./pages/PolicyDetail";
import CodebaseIntelligence from "./pages/CodebaseIntelligence";
import ScanHistory from "./pages/ScanHistory";
import Settings from "./pages/Settings";

function App() {
  return (
    <ErrorBoundary>
    <AuthProvider>
      <ProjectProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route path="/" element={<Dashboard />} />
                <Route path="/policies" element={<Policies />} />
                <Route path="/policies/:id" element={<PolicyDetail />} />
                <Route
                  path="/intelligence"
                  element={<CodebaseIntelligence />}
                />
                <Route path="/scans" element={<ScanHistory />} />
                <Route path="/settings" element={<Settings />} />
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster richColors />
      </ProjectProvider>
    </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
