import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { X, ArrowUp, Info } from "lucide-react";
import { message } from "../app/state";
export function ErrorNotice({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  return (
    <div className="notice error" role="alert">
      <span>{message(error)}</span>
      {retry && (
        <button className="text-button" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}
export function Loading({ text = "Loading…" }: { text?: string }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" />
      {text}
    </div>
  );
}
export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action}
    </header>
  );
}
export function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const el = ref.current;
    const previous = document.activeElement as HTMLElement;
    el?.showModal();
    return () => {
      el?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      className={wide ? "modal wide" : "modal"}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-heading">
        <h2 id={titleId}>{title}</h2>
        <button className="icon-button" aria-label="Close" onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Hint({ id, children }: { id: string; children: ReactNode }) {
  const [hidden, setHidden] = useState(
    () => localStorage.getItem(`policyiq:hint:${id}`) === "done",
  );
  if (hidden) return null;
  return (
    <aside className="hint" aria-label="Helpful tip">
      <Info size={17} />
      <span>{children}</span>
      <button
        className="text-button"
        onClick={() => {
          localStorage.setItem(`policyiq:hint:${id}`, "done");
          setHidden(true);
        }}
      >
        Got it
      </button>
      <button
        className="icon-button"
        aria-label="Skip this hint"
        onClick={() => {
          localStorage.setItem(`policyiq:hint:${id}`, "done");
          setHidden(true);
        }}
      >
        <X size={16} />
      </button>
    </aside>
  );
}
export function QuestionComposer({
  onSubmit,
  pending = false,
  initial = "",
  compact = false,
}: {
  onSubmit: (value: string) => void;
  pending?: boolean;
  initial?: string;
  compact?: boolean;
}) {
  const [value, setValue] = useState(initial);
  return (
    <form
      className={`composer ${compact ? "compact" : ""}`}
      onSubmit={(e) => {
        e.preventDefault();
        if (value.trim()) onSubmit(value.trim());
      }}
    >
      <label className="sr-only" htmlFor="question">
        Your policy question
      </label>
      <textarea
        id="question"
        value={value}
        maxLength={2000}
        onChange={(e) => setValue(e.target.value)}
        placeholder="What would you like to know about your policy?"
        rows={compact ? 2 : 3}
        required
      />
      <div className="composer-bottom">
        <span>Answers grounded in your policy</span>
        <button
          className="button primary"
          disabled={pending || !value.trim()}
          type="submit"
        >
          {pending ? "Checking evidence…" : "Ask question"}
          <ArrowUp size={17} />
        </button>
      </div>
    </form>
  );
}
export const formatDate = (date: string) =>
  new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(date));
