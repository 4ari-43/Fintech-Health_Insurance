import { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, useLocation } from "react-router";
import {
  Files,
  MessageSquare,
  ClipboardList,
  LifeBuoy,
  Settings,
  Menu,
  ChevronRight,
} from "lucide-react";
import { isDemo } from "../api";
import { useSession, queryClient, isUnauthorized } from "./state";
import { ErrorNotice, Loading, Modal } from "../shared/ui";
const destinations = [
  { to: "/policies", label: "My Policies", Icon: Files },
  { to: "/ask", label: "Ask Policy", Icon: MessageSquare },
  { to: "/claims", label: "Claim Preparation", Icon: ClipboardList },
];
function Navigation({ close }: { close?: () => void }) {
  const { data } = useSession();
  return (
    <>
      <NavLink to="/policies" className="wordmark" onClick={close}>
        Policy<span>IQ</span>
        <span className="wordmark-dot" />
      </NavLink>
      <div className="nav-caption">YOUR WORKSPACE</div>
      <nav aria-label="Main navigation">
        {destinations.map(({ to, label, Icon }) => (
          <NavLink key={to} to={to} onClick={close}>
            <Icon size={19} />
            <span>{label}</span>
            <ChevronRight className="nav-arrow" size={14} />
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <nav aria-label="Support and account">
          <NavLink to="/guide" onClick={close}>
            <LifeBuoy size={19} />
            Help & guide
          </NavLink>
          <NavLink to="/settings" onClick={close}>
            <Settings size={19} />
            Account & Privacy
          </NavLink>
        </nav>
        <div className="profile">
          <div className="avatar">{data?.user.name.slice(0, 1) || "P"}</div>
          <div>
            <strong>{data?.user.name}</strong>
            <span>{isDemo ? "Demo account" : "Personal workspace"}</span>
          </div>
        </div>
      </div>
    </>
  );
}
export function Shell() {
  const { data, isPending, error } = useSession();
  const [drawer, setDrawer] = useState(false);
  const [expiredSession, setExpiredSession] = useState(false);
  const location = useLocation();
  useEffect(() => {
    const listener = () => {
      setExpiredSession(true);
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
      queryClient.setQueryData(["session"], null);
      window.dispatchEvent(new Event("policyiq:clear"));
    };
    window.addEventListener("policyiq:expired", listener);
    return () => window.removeEventListener("policyiq:expired", listener);
  }, []);
  useEffect(() => {
    document.getElementById("main-content")?.scrollTo(0, 0);
  }, [location.pathname]);
  if (isPending && !expiredSession) return <Loading />;
  if (error && !isUnauthorized(error))
    return (
      <div className="fatal">
        <ErrorNotice
          error={error}
          retry={() => queryClient.invalidateQueries({ queryKey: ["session"] })}
        />
      </div>
    );
  if (expiredSession || isUnauthorized(error) || !data)
    return (
      <Navigate
        to="/login"
        state={{ expired: expiredSession || !!error, from: location.pathname }}
        replace
      />
    );
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar" aria-label="Sidebar navigation">
        <Navigation />
      </aside>
      <div className="main-column">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label="Open navigation"
            onClick={() => setDrawer(true)}
          >
            <Menu size={22} />
          </button>
          <span className="topbar-label">Health insurance, made clearer</span>
          <span className={isDemo ? "mode-tag" : "workspace-tag"}>
            {isDemo ? "Demo workspace" : "Personal workspace"}
          </span>
        </header>
        <main id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
        <footer className="app-footer">
          PolicyIQ helps you understand the wording. Your insurer confirms
          coverage.
        </footer>
      </div>
      {drawer && (
        <Modal title="Navigation" onClose={() => setDrawer(false)}>
          <div className="drawer-nav">
            <Navigation close={() => setDrawer(false)} />
          </div>
        </Modal>
      )}
    </div>
  );
}
