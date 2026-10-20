import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import {
  ArrowRight,
  ArrowLeft,
  Check,
  Download,
  Plus,
  ClipboardList,
  Trash2,
} from "lucide-react";
import { api, isDemo } from "../../api";
import type { Claim, ClaimInput } from "../../api/contracts";
import { queryClient, usePolicies, useSelection } from "../../app/state";
import {
  ErrorNotice,
  Hint,
  Loading,
  PageHeader,
  formatDate,
  Modal,
} from "../../shared/ui";
import { suggestedDocuments, preparationProgress, downloadText } from "./rules";
const schema = z.object({
  policy_id: z.string().min(1, "Choose a policy."),
  description: z.string().trim().min(3, "Add a brief description.").max(4000),
  incident_date: z
    .string()
    .min(1, "Choose the incident date.")
    .refine(
      (v) => v >= "1900-01-01" && new Date(v + "T00:00:00") <= new Date(),
      "Choose today or an earlier date.",
    ),
  gathered: z.array(z.string()),
});
export function ClaimsPage() {
  const policies = usePolicies();
  const drafts = useQuery({ queryKey: ["claims"], queryFn: api.claims });
  const [params] = useSearchParams();
  const { selected } = useSelection();
  const [editing, setEditing] = useState<Claim | "new" | null>(
    params.get("policy") ? "new" : null,
  );
  const [deleting, setDeleting] = useState<Claim>();
  const remove = useMutation({
    mutationFn: api.deleteClaim,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["claims"] });
      setDeleting(undefined);
    },
  });
  if (policies.isPending || drafts.isPending) return <Loading />;
  if (policies.error || drafts.error)
    return (
      <ErrorNotice
        error={policies.error || drafts.error}
        retry={() => {
          policies.refetch();
          drafts.refetch();
        }}
      />
    );
  const available = policies.data || [];
  return (
    <>
      <PageHeader
        eyebrow="CLAIM PREPARATION"
        title={
          editing ? "One step closer to ready." : "Get your paperwork in order."
        }
        description="A preparation workspace. Nothing is submitted to your insurer."
        action={
          !editing &&
          available.length > 0 && (
            <button
              className="button primary"
              onClick={() => setEditing("new")}
            >
              <Plus size={17} />
              Prepare a claim
            </button>
          )
        }
      />
      {!available.length ? (
        <div className="empty-small">
          <ClipboardList size={32} />
          <h2>Start with your policy</h2>
          <p>Add a document so your claim draft stays connected to it.</p>
          <Link className="button primary" to="/policies">
            Add your policy
            <ArrowRight size={17} />
          </Link>
        </div>
      ) : editing ? (
        <ClaimWorkspace
          key={typeof editing === "string" ? "new" : editing.id}
          draft={editing === "new" ? undefined : editing}
          defaultPolicy={params.get("policy") || selected || available[0].id}
          policies={available}
          onClose={() => setEditing(null)}
        />
      ) : drafts.data?.length ? (
        <div className="draft-list">
          {drafts.data.map((c) => (
            <article className="draft-row" key={c.id}>
              <div>
                <span className="badge neutral">Saved draft</span>
                <h2>{c.description}</h2>
                <p>
                  {available.find((p) => p.id === c.policy_id)?.filename} ·
                  Incident {formatDate(c.incident_date)}
                </p>
              </div>
              <button className="button" onClick={() => setEditing(c)}>
                Continue
                <ArrowRight size={16} />
              </button>
              <button
                className="icon-button"
                aria-label="Delete claim draft"
                onClick={() => setDeleting(c)}
              >
                <Trash2 size={17} />
              </button>
            </article>
          ))}
        </div>
      ) : (
        <div className="claim-intro">
          <div className="file-symbol">
            <ClipboardList size={38} strokeWidth={1.3} />
          </div>
          <h2>Begin with what happened.</h2>
          <p>
            Add the details, gather your documents, then export a clear summary.
          </p>
          <ol>
            <li>
              <span>1</span>Details
            </li>
            <li>
              <span>2</span>Documents
            </li>
            <li>
              <span>3</span>Review
            </li>
          </ol>
          <button className="button primary" onClick={() => setEditing("new")}>
            Prepare a claim
            <ArrowRight size={17} />
          </button>
        </div>
      )}
      {deleting && (
        <Modal
          title="Delete this draft?"
          onClose={() => setDeleting(undefined)}
        >
          <p>
            The saved details and gathered-document checklist will be removed.
          </p>
          <div className="row-actions modal-actions">
            <button className="button" onClick={() => setDeleting(undefined)}>
              Keep draft
            </button>
            <button
              className="button danger"
              onClick={() => remove.mutate(deleting.id)}
            >
              Delete draft
            </button>
          </div>
          {remove.error && <ErrorNotice error={remove.error} />}
        </Modal>
      )}
    </>
  );
}
function ClaimWorkspace({
  draft,
  defaultPolicy,
  policies,
  onClose,
}: {
  draft?: Claim;
  defaultPolicy: string;
  policies: { id: string; filename: string }[];
  onClose: () => void;
}) {
  const [step, setStep] = useState(0);
  const [saved, setSaved] = useState<Claim | undefined>(draft);
  const [discard, setDiscard] = useState(false);
  const form = useForm<ClaimInput>({
    resolver: zodResolver(schema),
    defaultValues: draft || {
      policy_id: defaultPolicy,
      description: "",
      incident_date: "",
      gathered: [],
    },
  });
  const [policy_id, description, incident_date, gathered] = useWatch({
    control: form.control,
    name: ["policy_id", "description", "incident_date", "gathered"],
  });
  const values = { policy_id, description, incident_date, gathered };
  const progress = preparationProgress(
    values.description,
    values.incident_date,
    values.gathered,
  );
  const save = useMutation({
    mutationFn: (data: ClaimInput) => api.saveClaim(data, saved?.id),
    onSuccess: (c) => {
      setSaved(c);
      form.reset(c);
      queryClient.invalidateQueries({ queryKey: ["claims"] });
    },
  });
  async function next() {
    if (await form.trigger()) {
      await save
        .mutateAsync(form.getValues())
        .then(() => setStep(Math.min(2, step + 1)))
        .catch(() => {});
    }
  }
  async function saveClose() {
    if (await form.trigger()) {
      await save
        .mutateAsync(form.getValues())
        .then(onClose)
        .catch(() => {});
    }
  }
  const first = suggestedDocuments.find((d) => !values.gathered.includes(d.id));
  return (
    <>
      <ol className="claim-steps" aria-label="Preparation steps">
        {["Details", "Documents", "Review"].map((label, i) => (
          <li
            className={step === i ? "current" : step > i ? "completed" : ""}
            key={label}
            aria-current={step === i ? "step" : undefined}
          >
            <span>{step > i ? <Check size={15} /> : i + 1}</span>
            {label}
          </li>
        ))}
      </ol>
      <div className="claim-workspace">
        <section className="panel claim-main">
          {step === 0 ? (
            <>
              <h2>Tell us what happened</h2>
              <p className="section-intro">
                Just the essentials to start your draft.
              </p>
              <form
                className="form-stack"
                onSubmit={(e) => {
                  e.preventDefault();
                  next();
                }}
              >
                <div>
                  <label htmlFor="claim-policy">Policy</label>
                  <select id="claim-policy" {...form.register("policy_id")}>
                    {policies.map((p) => (
                      <option value={p.id} key={p.id}>
                        {p.filename}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="incident">Brief incident description</label>
                  <textarea
                    id="incident"
                    rows={4}
                    placeholder="For example, an overnight hospital stay following an injury."
                    {...form.register("description")}
                    aria-invalid={!!form.formState.errors.description}
                  />
                  {form.formState.errors.description && (
                    <p className="field-error" role="alert">
                      {form.formState.errors.description.message}
                    </p>
                  )}
                </div>
                <div>
                  <label htmlFor="incident-date">Incident date</label>
                  <input
                    id="incident-date"
                    type="date"
                    {...form.register("incident_date")}
                    aria-invalid={!!form.formState.errors.incident_date}
                  />
                  {form.formState.errors.incident_date && (
                    <p className="field-error" role="alert">
                      {form.formState.errors.incident_date.message}
                    </p>
                  )}
                </div>
                <button className="button primary" disabled={save.isPending}>
                  {save.isPending ? "Saving…" : "Continue to documents"}
                  <ArrowRight size={17} />
                </button>
              </form>
            </>
          ) : step === 1 ? (
            <>
              <h2>Gather your documents</h2>
              <p className="section-intro">
                Mark an item when you have it ready. Files stay with you.
              </p>
              <Hint id="claim">
                Gathered means you have the document. No claim files are
                uploaded to this workspace.
              </Hint>
              <div className="requirements-note">
                <strong>Required by your policy</strong>
                <p>
                  Not established. Confirm the exact requirements with your
                  insurer.
                </p>
              </div>
              <h3 className="checklist-heading">Recommended to gather</h3>
              {suggestedDocuments.map((item) => (
                <label className="checklist-item" key={item.id}>
                  <input
                    type="checkbox"
                    checked={values.gathered.includes(item.id)}
                    onChange={(e) =>
                      form.setValue(
                        "gathered",
                        e.target.checked
                          ? [...values.gathered, item.id]
                          : values.gathered.filter((x) => x !== item.id),
                        { shouldDirty: true },
                      )
                    }
                  />
                  <span>
                    <strong>{item.label}</strong>
                    <span>{item.detail}</span>
                    <small>
                      {values.gathered.includes(item.id)
                        ? "Marked as gathered · not uploaded"
                        : "Not gathered"}
                    </small>
                  </span>
                </label>
              ))}
              <p className="meta">
                These are general organizational suggestions, not extracted
                policy obligations.
              </p>
              <div className="step-actions">
                <button className="button" onClick={() => setStep(0)}>
                  <ArrowLeft size={16} />
                  Back
                </button>
                <button
                  className="button primary"
                  disabled={save.isPending}
                  onClick={next}
                >
                  Review summary
                  <ArrowRight size={16} />
                </button>
              </div>
            </>
          ) : (
            <>
              <h2>Review your preparation</h2>
              <p className="section-intro">
                Check the details before downloading your summary.
              </p>
              <dl className="review-details">
                <div>
                  <dt>Policy</dt>
                  <dd>
                    {policies.find((p) => p.id === values.policy_id)?.filename}
                  </dd>
                </div>
                <div>
                  <dt>Incident date</dt>
                  <dd>{formatDate(values.incident_date)}</dd>
                </div>
                <div>
                  <dt>What happened</dt>
                  <dd>{values.description}</dd>
                </div>
                <div>
                  <dt>Documents</dt>
                  <dd>
                    {values.gathered.length} of {suggestedDocuments.length}{" "}
                    suggestions marked as gathered. No files uploaded.
                  </dd>
                </div>
              </dl>
              <div className="notice">
                This summary is for preparation only. It is not a claim
                submission or an indication of approval.
              </div>
              <div className="step-actions">
                <button className="button" onClick={() => setStep(1)}>
                  <ArrowLeft size={16} />
                  Back
                </button>
                {saved &&
                  (isDemo ? (
                    <button
                      className="button primary"
                      onClick={() =>
                        downloadText(
                          "demo-claim-summary.txt",
                          `DEMO - Fictional workspace\nPreparation only. Not submitted.\nPolicy: ${policies.find((p) => p.id === values.policy_id)?.filename}\nIncident date: ${values.incident_date}\nDescription: ${values.description}\nGathered (not uploaded): ${values.gathered.map((id) => suggestedDocuments.find((d) => d.id === id)?.label).join(", ")}\nRequired documents and deadlines are not established.`,
                        )
                      }
                    >
                      <Download size={17} />
                      Export summary
                    </button>
                  ) : (
                    <a
                      className="button primary"
                      href={`/api/claims/${saved.id}/export`}
                      download
                    >
                      <Download size={17} />
                      Export summary
                    </a>
                  ))}
              </div>
            </>
          )}
          {save.error && <ErrorNotice error={save.error} />}
        </section>
        <aside className="claim-aside" aria-label="Claim preparation progress">
          <div className="eyebrow">YOUR PREPARATION</div>
          <div className="progress-value">
            {progress}
            <span>%</span>
          </div>
          <progress
            value={progress}
            max={100}
            aria-label="Preparation completeness"
          />
          <p className="meta">
            Details and suggested documents. This does not measure approval
            likelihood.
          </p>
          <div className="divider" />
          <span className="eyebrow">NEXT STEP</span>
          <h3>
            {step === 0
              ? "Add your incident details"
              : first
                ? `Gather ${first.label.toLowerCase()}`
                : "Review and export your summary"}
          </h3>
          <div className="divider" />
          <h3>Check the filing deadline</h3>
          <p>
            No deadline has been extracted. Confirm notice and filing dates with
            your insurer.
          </p>
          <Link className="text-button" to={`/ask?policy=${values.policy_id}`}>
            Ask your policy
          </Link>
        </aside>
      </div>
      <div className="draft-footer">
        <span role="status">
          {save.isPending
            ? "Saving draft…"
            : form.formState.isDirty
              ? "Unsaved changes"
              : saved
                ? isDemo
                  ? "Draft held in demo memory"
                  : "Draft saved to your workspace"
                : "Not yet saved"}
        </span>
        <div className="row-actions">
          <button
            className="text-button"
            onClick={() =>
              form.formState.isDirty ? setDiscard(true) : onClose()
            }
          >
            Back to drafts
          </button>
          <button
            className="button"
            disabled={save.isPending}
            onClick={saveClose}
          >
            Save & close
          </button>
        </div>
      </div>
      {discard && (
        <Modal title="Leave unsaved changes?" onClose={() => setDiscard(false)}>
          <p>Your last saved draft will remain available.</p>
          <div className="row-actions modal-actions">
            <button className="button" onClick={() => setDiscard(false)}>
              Keep editing
            </button>
            <button className="button" onClick={onClose}>
              Discard changes
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
