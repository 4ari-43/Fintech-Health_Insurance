import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link, useLocation, useNavigate } from "react-router";
import { Eye, EyeOff, ArrowRight, FileCheck2 } from "lucide-react";
import { api, isDemo } from "../../api";
import { queryClient } from "../../app/state";
import { ErrorNotice } from "../../shared/ui";
const schema = z.object({
  name: z.string().optional(),
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password.").max(128),
});
type Values = z.infer<typeof schema>;
export function AuthPage({ signup = false }: { signup?: boolean }) {
  const [show, setShow] = useState(false);
  const [error, setError] = useState<unknown>();
  const navigate = useNavigate();
  const location = useLocation();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", email: "", password: "" },
  });
  const submit = form.handleSubmit(async (values) => {
    setError(undefined);
    if (signup && values.password.length < 12) {
      form.setError("password", { message: "Use at least 12 characters." });
      return;
    }
    if (signup && !values.name?.trim()) {
      form.setError("name", { message: "Enter your name." });
      return;
    }
    try {
      const s = signup
        ? await api.signup(values.name!, values.email, values.password)
        : await api.login(values.email, values.password);
      queryClient.clear();
      queryClient.setQueryData(["session"], s);
      navigate("/policies", { replace: true });
    } catch (e) {
      setError(e);
      form.setValue("password", "");
    }
  });
  return (
    <div className="auth-layout">
      <aside className="auth-story" aria-label="PolicyIQ overview">
        <Link className="wordmark" to="/">
          Policy<span>IQ</span>
          <span className="wordmark-dot" />
        </Link>
        <div className="auth-story-body">
          <div className="document-symbol">
            <FileCheck2 size={48} strokeWidth={1} />
          </div>
          <h2>
            A little clarity.
            <br />A better next step.
          </h2>
          <p>
            Your health policy, the supporting sources, and the paperwork ahead.
            In one place.
          </p>
          <div className="auth-benefit">
            <span>01</span>Understand the important terms
          </div>
          <div className="auth-benefit">
            <span>02</span>Ask with the document beside you
          </div>
          <div className="auth-benefit">
            <span>03</span>Prepare your claim information
          </div>
        </div>
        <small>Your documents deserve careful answers.</small>
      </aside>
      <main className="auth-main">
        <div className="auth-form">
          <div className="eyebrow">YOUR POLICY WORKSPACE</div>
          <h1>{signup ? "Create your account" : "Log in to PolicyIQ"}</h1>
          <p>
            {signup
              ? "Start with your document. Take it one step at a time."
              : "Pick up where you left off."}
          </p>
          {isDemo && (
            <div className="notice">
              Demo workspace. Authentication is simulated and data stays in
              memory.
            </div>
          )}
          {location.state?.expired && (
            <div className="notice" role="status">
              Your session has ended. Log in to continue.
            </div>
          )}
          {!!error && <ErrorNotice error={error} />}
          <form className="form-stack" onSubmit={submit} noValidate>
            {signup && (
              <div>
                <label htmlFor="name">Name</label>
                <input
                  id="name"
                  autoComplete="name"
                  {...form.register("name")}
                  aria-invalid={!!form.formState.errors.name}
                />
                {form.formState.errors.name && (
                  <div className="field-error" role="alert">
                    {form.formState.errors.name.message}
                  </div>
                )}
              </div>
            )}
            <div>
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                {...form.register("email")}
                aria-invalid={!!form.formState.errors.email}
              />
              {form.formState.errors.email && (
                <div className="field-error" role="alert">
                  {form.formState.errors.email.message}
                </div>
              )}
            </div>
            <div>
              <label htmlFor="password">Password</label>
              <div className="password-field">
                <input
                  id="password"
                  type={show ? "text" : "password"}
                  autoComplete={signup ? "new-password" : "current-password"}
                  {...form.register("password")}
                  aria-invalid={!!form.formState.errors.password}
                />
                <button
                  className="icon-button"
                  type="button"
                  aria-label={show ? "Hide password" : "Show password"}
                  onClick={() => setShow(!show)}
                >
                  {show ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {signup && <small>At least 12 characters.</small>}
              {form.formState.errors.password && (
                <div className="field-error" role="alert">
                  {form.formState.errors.password.message}
                </div>
              )}
            </div>
            {!signup && (
              <Link className="text-button auth-forgot" to="/forgot-password">
                Forgot password?
              </Link>
            )}
            <button
              className="button primary"
              disabled={form.formState.isSubmitting}
            >
              {form.formState.isSubmitting
                ? "Please wait…"
                : signup
                  ? "Create account"
                  : "Log in"}
              <ArrowRight size={17} />
            </button>
          </form>
          <p className="auth-switch">
            {signup ? "Already have an account?" : "New to PolicyIQ?"}{" "}
            <Link to={signup ? "/login" : "/signup"} className="text-button">
              {signup ? "Log in" : "Create an account"}
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}
export function RecoveryPage({ reset = false }: { reset?: boolean }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token] = useState(
    () => new URLSearchParams(window.location.hash.slice(1)).get("token") || "",
  );
  const [show, setShow] = useState(false);
  const [error, setError] = useState<unknown>();
  const [result, setResult] = useState("");
  const [pending, setPending] = useState(false);
  return (
    <div className="recovery">
      <Link className="wordmark" to="/login">
        Policy<span>IQ</span>
      </Link>
      <div className="panel">
        <h1>{reset ? "Set a new password" : "Forgot your password?"}</h1>
        <p>
          {reset
            ? "Use at least 12 characters."
            : "Check the available reset method for your account."}
        </p>
        {!!error && <ErrorNotice error={error} />}
        {result ? (
          <div className="notice" role="status">
            {result}
          </div>
        ) : (
          <form
            className="form-stack"
            onSubmit={async (e) => {
              e.preventDefault();
              setError(undefined);
              setPending(true);
              try {
                if (reset) {
                  await api.reset(token, password);
                  window.history.replaceState(
                    null,
                    "",
                    window.location.pathname,
                  );
                  setResult("Password changed. Log in with your new password.");
                } else setResult((await api.forgot(email)).message);
              } catch (e) {
                setError(e);
              } finally {
                setPending(false);
                setPassword("");
              }
            }}
          >
            {reset ? (
              <div>
                <label htmlFor="new-password">New password</label>
                <div className="password-field">
                  <input
                    id="new-password"
                    autoComplete="new-password"
                    type={show ? "text" : "password"}
                    minLength={12}
                    maxLength={128}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={show ? "Hide password" : "Show password"}
                    onClick={() => setShow(!show)}
                  >
                    {show ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <label htmlFor="recovery-email">Email address</label>
                <input
                  id="recovery-email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            )}
            <button className="button primary" disabled={pending}>
              {pending
                ? "Please wait…"
                : reset
                  ? "Save new password"
                  : "Request reset instructions"}
            </button>
          </form>
        )}
        <Link className="back-link" to="/login">
          Back to log in
        </Link>
      </div>
    </div>
  );
}
