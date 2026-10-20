import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router";
import { Eye, EyeOff, LogOut, ArrowRight } from "lucide-react";
import { api, isDemo } from "../../api";
import { queryClient, useSession, useSelection } from "../../app/state";
import { PageHeader, ErrorNotice, Loading } from "../../shared/ui";
export function SettingsPage() {
  const { data } = useSession();
  const config = useQuery({ queryKey: ["config"], queryFn: api.config });
  const [name, setName] = useState(data?.user.name || "");
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [status, setStatus] = useState("");
  const navigate = useNavigate();
  const { select } = useSelection();
  const profile = useMutation({
    mutationFn: () => api.profile(name),
    onSuccess: (s) => {
      queryClient.setQueryData(["session"], s);
      setStatus("Profile saved.");
    },
  });
  const signout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      queryClient.clear();
      select("");
      navigate("/login", { replace: true });
    },
  });
  const change = useMutation({
    mutationFn: () => api.password(current, password),
    onSuccess: () => {
      queryClient.clear();
      select("");
      navigate("/login", { replace: true, state: { expired: true } });
    },
    onSettled: () => {
      setCurrent("");
      setPassword("");
    },
  });
  return (
    <>
      <PageHeader
        eyebrow="ACCOUNT & PRIVACY"
        title="Your workspace. Your information."
        description="Manage your profile and understand how your documents are handled."
      />
      <div className="settings-layout">
        <section className="panel">
          <h2>Profile</h2>
          <form
            className="form-stack"
            onSubmit={(e) => {
              e.preventDefault();
              profile.mutate();
            }}
          >
            <div>
              <label htmlFor="profile-name">Name</label>
              <input
                id="profile-name"
                autoComplete="name"
                maxLength={80}
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="profile-email">Email address</label>
              <input
                id="profile-email"
                type="email"
                autoComplete="email"
                value={data?.user.email || ""}
                readOnly
              />
              <small>Email changes are not available in this workspace.</small>
            </div>
            <button className="button" disabled={profile.isPending}>
              {profile.isPending ? "Saving…" : "Save profile"}
            </button>
            {profile.error && <ErrorNotice error={profile.error} />}
            {status && <p role="status">{status}</p>}
          </form>
        </section>
        <section className="privacy-section">
          <h2>How your data is used</h2>
          {config.isPending ? (
            <Loading />
          ) : config.error ? (
            <ErrorNotice error={config.error} retry={config.refetch} />
          ) : (
            <p>{config.data?.processing}</p>
          )}
          <p>
            {isDemo
              ? "Demo data is fictional and held in browser memory. Reloading or signing out clears it. Demo authentication does not secure real data."
              : "Your original PDFs, extracted passages, questions, answers, and claim drafts are stored on this server. Access is checked against your account."}
          </p>
          <details>
            <summary>Storage and deletion</summary>
            <p>
              {isDemo
                ? "No demo documents are uploaded. Hints use non-sensitive browser preferences."
                : "Deleting a policy removes its original, passages, conversations and linked claim drafts from the active database. Backups and database journals may retain data until their retention cycle ends. Files are not automatically redacted or encrypted by this application."}
            </p>
            <p>
              Browser storage holds hint preferences only. Session credentials
              use an HttpOnly cookie; document content is not saved to
              localStorage or IndexedDB.
            </p>
          </details>
          <Link className="text-button" to="/policies">
            Manage policy documents
            <ArrowRight size={15} />
          </Link>
        </section>
        <section className="panel">
          <h2>Change password</h2>
          <p className="section-intro">
            Changing your password ends your active sessions.
          </p>
          <form
            className="form-stack"
            onSubmit={(e) => {
              e.preventDefault();
              change.mutate();
            }}
          >
            <div>
              <label htmlFor="current-password">Current password</label>
              <input
                id="current-password"
                type={show ? "text" : "password"}
                autoComplete="current-password"
                required
                value={current}
                maxLength={128}
                onChange={(e) => setCurrent(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="change-password">New password</label>
              <div className="password-field">
                <input
                  id="change-password"
                  type={show ? "text" : "password"}
                  autoComplete="new-password"
                  required
                  minLength={12}
                  maxLength={128}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="icon-button"
                  aria-label={show ? "Hide passwords" : "Show passwords"}
                  onClick={() => setShow(!show)}
                >
                  {show ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              <small>At least 12 characters.</small>
            </div>
            <button className="button" disabled={change.isPending}>
              {change.isPending ? "Updating…" : "Change password"}
            </button>
            {change.error && <ErrorNotice error={change.error} />}
          </form>
        </section>
      </div>
      <div className="signout-row">
        <div>
          <h2>Sign out of this workspace</h2>
          <p>Your saved documents and drafts will remain on the server.</p>
        </div>
        <button
          className="button"
          disabled={signout.isPending}
          onClick={() => signout.mutate()}
        >
          <LogOut size={17} />
          Sign out
        </button>
      </div>
      {signout.error && <ErrorNotice error={signout.error} />}
    </>
  );
}
