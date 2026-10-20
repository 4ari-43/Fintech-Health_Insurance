import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";
import { ArrowLeft, FileText, ClipboardList, ArrowRight } from "lucide-react";
import { api, isDemo } from "../../api";
import { queryClient, useSelection } from "../../app/state";
import {
  PageHeader,
  ErrorNotice,
  Loading,
  QuestionComposer,
  Hint,
  formatDate,
} from "../../shared/ui";
import { DocumentViewer, SourcePanel } from "../questions/Sources";
import type { Source } from "../../api/contracts";
export function OverviewPage() {
  const { id = "" } = useParams();
  const { select } = useSelection();
  const navigate = useNavigate();
  const [viewer, setViewer] = useState(false);
  const [source, setSource] = useState<Source>();
  const {
    data: policy,
    error,
    isPending,
    refetch,
  } = useQuery({ queryKey: ["policy", id], queryFn: () => api.policy(id) });
  useEffect(() => {
    select(id);
    void api
      .opened(id)
      .then(() => queryClient.invalidateQueries({ queryKey: ["policies"] }))
      .catch(() => {});
  }, [id, select]);
  if (isPending) return <Loading text="Opening your policy…" />;
  if (error || !policy) return <ErrorNotice error={error} retry={refetch} />;
  return (
    <>
      <Link className="back-link" to="/policies">
        <ArrowLeft size={15} />
        My Policies
      </Link>
      <PageHeader
        eyebrow="POLICY OVERVIEW"
        title={policy.filename.replace(/\.pdf$/i, "")}
        description="Start with the question on your mind."
        action={
          <button className="button" onClick={() => setViewer(true)}>
            <FileText size={17} />
            {policy.original_available
              ? "View document"
              : "View sample excerpt"}
          </button>
        }
      />
      <QuestionComposer
        onSubmit={(question) =>
          navigate(`/ask?policy=${id}`, { state: { question } })
        }
      />
      <Hint id="question">
        Be specific about the treatment, provider network, or cost you want to
        understand.
      </Hint>
      <div className="document-facts">
        <div>
          <span>Document length</span>
          <strong>
            {policy.page_count} {policy.page_count === 1 ? "page" : "pages"}
          </strong>
        </div>
        <div>
          <span>Added to workspace</span>
          <strong>{formatDate(policy.created_at)}</strong>
        </div>
        <div>
          <span>Document status</span>
          <strong>
            {policy.warnings.length ? "Review notes" : "Text ready"}
          </strong>
        </div>
      </div>
      {isDemo ? (
        <section className="sample-terms">
          <div>
            <span className="eyebrow">ILLUSTRATIVE KEY TERM</span>
            <h2>Individual deductible</h2>
            <p>Fictional sample · Annual · In network · USD</p>
          </div>
          <div>
            <strong>$750</strong>
            <button
              className="text-button"
              onClick={async () => {
                const { sampleText } = await import("../../api/demo");
                setSource({
                  policy_id: id,
                  passage_id: id + "-p1",
                  page_start: 1,
                  page_end: 1,
                  section: "Sample terms",
                  text: sampleText,
                  quote: "The individual in-network annual deductible is $750.",
                });
              }}
            >
              View source · p. 1
            </button>
          </div>
        </section>
      ) : (
        <section className="overview-note">
          <h2>Get the terms that matter to you</h2>
          <p>
            Ask about a deductible, an exclusion, or a treatment. Financial
            terms have not been automatically extracted from this document.
          </p>
        </section>
      )}
      <section className="policy-details">
        {policy.warnings.length > 0 && (
          <details open>
            <summary>
              Important document notes{" "}
              <span className="badge warning">{policy.warnings.length}</span>
            </summary>
            <ul>
              {policy.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </details>
        )}
        <details>
          <summary>Coverage & exclusions</summary>
          <p>
            Use a specific question to find relevant evidence. Retrieved wording
            alone does not establish coverage.
          </p>
          <div className="row-actions">
            <Link className="text-button" to={`/ask?policy=${id}`}>
              Ask about coverage
            </Link>
            <button className="text-button" onClick={() => setViewer(true)}>
              Read the document
            </button>
          </div>
        </details>
      </section>
      <Link className="compare-link" to={`/claims?policy=${id}`}>
        <ClipboardList size={22} />
        <div>
          <strong>Preparing to make a claim?</strong>
          <span>Start with the details. Keep your paperwork organized.</span>
        </div>
        <ArrowRight size={19} />
      </Link>
      {viewer && (
        <DocumentViewer policyId={id} onClose={() => setViewer(false)} />
      )}
      {source && (
        <SourcePanel source={source} onClose={() => setSource(undefined)} />
      )}
    </>
  );
}
