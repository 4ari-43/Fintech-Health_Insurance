import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link } from "react-router";
import { ArrowLeft, GitCompareArrows } from "lucide-react";
import { api } from "../../api";
import type { Source } from "../../api/contracts";
import { usePolicies } from "../../app/state";
import { PageHeader, ErrorNotice, Loading } from "../../shared/ui";
import { SourceButtons, SourcePanel } from "../questions/Sources";
const labels = {
  supported: "Relevant text found",
  uncertain: "Multiple values — review required",
  not_found: "Not established in retrieved text",
};
export function ComparisonPage() {
  const policies = usePolicies();
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [source, setSource] = useState<Source>();
  const compare = useMutation({ mutationFn: () => api.compare(a, b) });
  const all = policies.data || [];
  return (
    <>
      <Link className="back-link" to="/policies">
        <ArrowLeft size={15} />
        My Policies
      </Link>
      <PageHeader
        eyebrow="POLICY COMPARISON"
        title="Look at the wording side by side."
        description="Compare the evidence, with room for what is still uncertain."
      />
      {policies.isPending ? (
        <Loading />
      ) : policies.error ? (
        <ErrorNotice error={policies.error} retry={policies.refetch} />
      ) : all.length < 2 ? (
        <div className="empty-small">
          <h2>Two policies make a comparison</h2>
          <p>Upload another document to put their terms side by side.</p>
          <Link className="button primary" to="/policies">
            My Policies
          </Link>
        </div>
      ) : (
        <>
          <form
            className="comparison-selection panel"
            onSubmit={(e) => {
              e.preventDefault();
              compare.mutate();
            }}
          >
            <div>
              <label htmlFor="policy-a">First policy</label>
              <select
                id="policy-a"
                required
                value={a}
                onChange={(e) => {
                  setA(e.target.value);
                  compare.reset();
                }}
              >
                <option value="">Choose a policy</option>
                {all.map((p) => (
                  <option key={p.id} value={p.id} disabled={p.id === b}>
                    {p.filename}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="policy-b">Second policy</label>
              <select
                id="policy-b"
                required
                value={b}
                onChange={(e) => {
                  setB(e.target.value);
                  compare.reset();
                }}
              >
                <option value="">Choose a policy</option>
                {all.map((p) => (
                  <option key={p.id} value={p.id} disabled={p.id === a}>
                    {p.filename}
                  </option>
                ))}
              </select>
            </div>
            <button
              className="button primary"
              disabled={compare.isPending || !a || !b || a === b}
            >
              <GitCompareArrows size={18} />
              {compare.isPending ? "Comparing…" : "Compare policies"}
            </button>
          </form>
          {compare.error && (
            <ErrorNotice error={compare.error} retry={() => compare.mutate()} />
          )}
          {compare.data && (
            <>
              <div className="notice">
                Amounts may refer to different benefits, currencies, networks or
                tiers. No reliable difference or ranking is established.
              </div>
              <div className="comparison-results">
                <div className="comparison-title-row">
                  <span>Evidence by topic</span>
                  <strong>{all.find((p) => p.id === a)?.filename}</strong>
                  <strong>{all.find((p) => p.id === b)?.filename}</strong>
                </div>
                {compare.data.categories.map((category) => (
                  <section className="comparison-row" key={category.category}>
                    <h2>{category.label}</h2>
                    {[category.finding_a, category.finding_b].map(
                      (finding, i) => (
                        <div className="comparison-finding" key={i}>
                          <span className="mobile-policy-label">
                            {
                              all.find((p) => p.id === (i === 0 ? a : b))
                                ?.filename
                            }
                          </span>
                          <span
                            className={`badge ${finding.status === "supported" ? "" : finding.status === "uncertain" ? "warning" : "neutral"}`}
                          >
                            {labels[finding.status]}
                          </span>
                          {finding.amounts.length > 0 && (
                            <p className="comparison-amounts">
                              {finding.amounts.join(" · ")}
                            </p>
                          )}
                          <p>{finding.summary}</p>
                          <SourceButtons
                            sources={finding.evidence}
                            onSelect={setSource}
                          />
                        </div>
                      ),
                    )}
                  </section>
                ))}
              </div>
              <details>
                <summary>Comparison limitations</summary>
                {compare.data.limitations.map((x) => (
                  <p key={x}>{x}</p>
                ))}
              </details>
            </>
          )}
        </>
      )}
      {source && (
        <SourcePanel source={source} onClose={() => setSource(undefined)} />
      )}
    </>
  );
}
