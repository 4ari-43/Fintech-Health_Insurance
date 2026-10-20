import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { QueryClientProvider } from "@tanstack/react-query";
import { Shell } from "./Shell";
import { GuidePage } from "../features/guide/Guide";
import { SettingsPage } from "../features/settings/Settings";
import { ClaimsPage } from "../features/claims/Claims";
import { ComparisonPage } from "../features/comparison/Comparison";
import { OverviewPage } from "../features/policies/Overview";
import { AskPage } from "../features/questions/Ask";
import { PoliciesPage } from "../features/policies/Policies";
import { AuthPage, RecoveryPage } from "../features/auth/Auth";
import { ErrorBoundary, SelectionProvider, queryClient } from "./state";

export function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <SelectionProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<AuthPage />} />
              <Route path="/signup" element={<AuthPage signup />} />
              <Route path="/forgot-password" element={<RecoveryPage />} />
              <Route path="/reset-password" element={<RecoveryPage reset />} />
              <Route element={<Shell />}>
                <Route path="/policies" element={<PoliciesPage />} />
                <Route path="/policies/:id" element={<OverviewPage />} />
                <Route path="/ask" element={<AskPage />} />
                <Route path="/claims" element={<ClaimsPage />} />
                <Route path="/compare" element={<ComparisonPage />} />
                <Route path="/guide" element={<GuidePage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Route>
              <Route path="*" element={<Navigate to="/policies" replace />} />
            </Routes>
          </BrowserRouter>
        </SelectionProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
