import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router";
import {
  ArrowRight,
  FileText,
  Plus,
  Search,
  ArrowUpRight,
  Archive,
  Trash2,
  GitCompareArrows,
} from "lucide-react";
import { api, isDemo } from "../../api";
import type { Policy } from "../../api/contracts";
import { queryClient, usePolicies, useSelection } from "../../app/state";
import {
  PageHeader,
  Loading,
  ErrorNotice,
  Modal,
  formatDate,
} from "../../shared/ui";
import { UploadPanel } from "./Upload";
export function PoliciesPage() {
  const { data: policies, isPending, error, refetch } = usePolicies();
  const [search, setSearch] = useState("");
  const [archived, setArchived] = useState(false);
  const [upload, setUpload] = useState(false);
  const [deleting, setDeleting] = useState<Policy>();
  const { select } = useSelection();
  const navigate = useNavigate();
  const change = useMutation({
    mutationFn: ({
      id,
      remove,
      archive,
    }: {
      id: string;
      remove?: boolean;
      archive?: boolean;
    }) => (remove ? api.deletePolicy(id) : api.archive(id, !!archive)),
    onSuccess: (_result, variables) => {
      setDeleting(undefined);
      if (variables.remove) {
        queryClient.removeQueries({ queryKey: ["policy", variables.id] });
        queryClient.removeQueries({
          queryKey: ["conversations", variables.id],
        });
        queryClient.removeQueries({ queryKey: ["page", variables.id] });
        queryClient.invalidateQueries({ queryKey: ["claims"] });
      }
      queryClient.invalidateQueries({ queryKey: ["policies"] });
    },
  });
  if (isPending) return <Loading text="Loading your policies…" />;
  if (error) return <ErrorNotice error={error} retry={refetch} />;
  const all = policies || [];
  const shown = all.filter(
    (p) =>
      p.archived === archived &&
      p.filename.toLowerCase().includes(search.toLowerCase()),
  );
  const recent = all
    .filter((p) => p.last_opened && !p.archived)
    .sort((a, b) => b.last_opened!.localeCompare(a.last_opened!))[0];
  function open(p: Policy) {
    select(p.id);
    navigate(`/policies/${p.id}`);
  }
  return (
    <>
      <PageHeader
        eyebrow="MY POLICIES"
        title={
          all.length
            ? "Your policies, in one place."
            : "Start with your policy."
        }
        description={
          all.length
            ? "Open a document to understand the terms or ask a question."
            : "Upload your PDF to get straight to the important terms."
        }
        action={
          all.length > 0 && (
            <button className="button primary" onClick={() => setUpload(true)}>
              <Plus size={18} />
              Upload policy
            </button>
          )
        }
      />
      {!all.length ? (
        <>
          <UploadPanel large />
          {isDemo && (
            <div className="sample-action">
              <span>Just taking a look?</span>
              <button
                className="text-button"
                onClick={async () => {
                  (await import("../../api/demo")).loadSamples();
                  refetch();
                }}
              >
                Explore sample policies <ArrowRight size={15} />
              </button>
            </div>
          )}
          <div className="first-use-steps">
            <div>
              <span>01</span>
              <strong>Add your document</strong>
              <p>Keep the original close at hand.</p>
            </div>
            <div>
              <span>02</span>
              <strong>Ask what matters</strong>
              <p>See the wording behind each answer.</p>
            </div>
            <div>
              <span>03</span>
              <strong>Prepare your next step</strong>
              <p>Organize information for a claim.</p>
            </div>
          </div>
          <Link className="guide-link" to="/guide">
            <span>
              Looking for insurance? <strong>Find where to start.</strong>
            </span>
            <ArrowUpRight size={19} />
          </Link>
        </>
      ) : (
        <>
          {recent && !search && !archived && (
            <section className="continue-panel">
              <div className="continue-icon">
                <FileText size={26} strokeWidth={1.4} />
              </div>
              <div>
                <span className="eyebrow">CONTINUE WITH</span>
                <h2>{recent.filename.replace(/\.pdf$/i, "")}</h2>
                <p>Last opened {formatDate(recent.last_opened!)}</p>
              </div>
              <button className="button" onClick={() => open(recent)}>
                Open policy
                <ArrowRight size={17} />
              </button>
            </section>
          )}
          <div className="policy-toolbar">
            <div className="tabs" aria-label="Policy status">
              <button
                className={!archived ? "active" : ""}
                onClick={() => setArchived(false)}
              >
                Active <span>{all.filter((p) => !p.archived).length}</span>
              </button>
              <button
                className={archived ? "active" : ""}
                onClick={() => setArchived(true)}
              >
                Archived <span>{all.filter((p) => p.archived).length}</span>
              </button>
            </div>
            <div className="search-field">
              <Search size={17} />
              <input
                aria-label="Search policies"
                placeholder="Search your policies"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          {change.error && <ErrorNotice error={change.error} />}
          <div className="policy-list">
            {shown.length ? (
              shown.map((p) => (
                <article className="policy-row" key={p.id}>
                  <div className="policy-file-icon">
                    <FileText size={26} strokeWidth={1.3} />
                  </div>
                  <button className="policy-row-main" onClick={() => open(p)}>
                    <strong>{p.filename.replace(/\.pdf$/i, "")}</strong>
                    <span>
                      {p.page_count} {p.page_count === 1 ? "page" : "pages"}
                      <i />
                      Added {formatDate(p.created_at)}
                    </span>
                  </button>
                  <span
                    className={`badge ${p.warnings.length ? "warning" : ""}`}
                  >
                    {p.warnings.length ? "Review notes" : "Ready to explore"}
                  </span>
                  <div className="policy-row-actions">
                    <button
                      className="icon-button"
                      aria-label={
                        p.archived
                          ? `Restore ${p.filename}`
                          : `Archive ${p.filename}`
                      }
                      disabled={change.isPending}
                      onClick={() =>
                        change.mutate({ id: p.id, archive: !p.archived })
                      }
                    >
                      <Archive size={17} />
                    </button>
                    <button
                      className="icon-button"
                      aria-label={`Delete ${p.filename}`}
                      onClick={() => setDeleting(p)}
                    >
                      <Trash2 size={17} />
                    </button>
                    <button
                      className="icon-button"
                      aria-label={`Open ${p.filename}`}
                      onClick={() => open(p)}
                    >
                      <ArrowRight size={19} />
                    </button>
                  </div>
                </article>
              ))
            ) : (
              <div className="empty-small">
                <h2>
                  {search ? "No matching policies" : "No archived policies"}
                </h2>
                <p>
                  {search
                    ? "Try a different document name."
                    : "Archived documents will appear here."}
                </p>
              </div>
            )}
          </div>
          {all.length >= 2 && (
            <Link className="compare-link" to="/compare">
              <GitCompareArrows size={20} />
              <div>
                <strong>Put two policies side by side</strong>
                <span>Compare the wording, with sources for each finding.</span>
              </div>
              <ArrowRight size={19} />
            </Link>
          )}
        </>
      )}
      {upload && (
        <Modal title="Upload a policy" onClose={() => setUpload(false)}>
          <UploadPanel onDone={() => setUpload(false)} />
        </Modal>
      )}
      {deleting && (
        <Modal
          title="Delete this policy?"
          onClose={() => setDeleting(undefined)}
        >
          <p>
            <strong>{deleting.filename}</strong> and its original PDF, passages,
            conversations, and related claim drafts will be removed. This cannot
            be undone.
          </p>
          <div className="row-actions modal-actions">
            <button className="button" onClick={() => setDeleting(undefined)}>
              Keep policy
            </button>
            <button
              className="button danger"
              disabled={change.isPending}
              onClick={() => change.mutate({ id: deleting.id, remove: true })}
            >
              {change.isPending ? "Deleting…" : "Delete policy"}
            </button>
          </div>
          {change.error && <ErrorNotice error={change.error} />}
        </Modal>
      )}
    </>
  );
}
