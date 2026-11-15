import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Layout from "./components/Layout";
import { ErrorBoundary } from "./components/ErrorBoundary";
import Home from "./pages/Home";
import "./styles/index.css";
import NewRun from "./pages/NewRun";
const LiveRun = lazy(() => import("./pages/LiveRun"));
const History = lazy(() => import("./pages/History"));
const Evaluation = lazy(() => import("./pages/Evaluation"));
const About = lazy(() => import("./pages/About"));
const query = new QueryClient({
  defaultOptions: { queries: { staleTime: 10000, retry: false } },
});
function Loading() {
  return (
    <div className="page">
      <div className="skeleton skeleton-heading" />
      <div className="skeleton skeleton-card" />
      <div className="skeleton skeleton-card" />
    </div>
  );
}
function NotFound() {
  return (
    <div className="page empty-state">
      <h1>This route took a wrong turn.</h1>
      <p>The page or run you’re looking for could not be found.</p>
      <a className="button button-primary" href="/">
        Back to workspace
      </a>
    </div>
  );
}
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={query}>
        <BrowserRouter>
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route element={<Layout />}>
                <Route index element={<Home />} />
                <Route path="new" element={<NewRun />} />
                <Route path="run/:id" element={<LiveRun />} />
                <Route path="runs" element={<History />} />
                <Route path="evaluation" element={<Evaluation />} />
                <Route path="about" element={<About />} />
                <Route path="*" element={<NotFound />} />
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
