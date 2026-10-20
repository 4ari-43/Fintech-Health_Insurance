import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
} from "lucide-react";
import { api } from "../../api";
import type { Source } from "../../api/contracts";
import { ErrorNotice, Hint, Loading, Modal } from "../../shared/ui";
function Highlight({ text, quote }: { text: string; quote?: string }) {
  if (!quote || !text.includes(quote)) return <>{text}</>;
  const i = text.indexOf(quote);
  return (
    <>
      {text.slice(0, i)}
      <mark>{quote}</mark>
      {text.slice(i + quote.length)}
    </>
  );
}
export function DocumentViewer({
  policyId,
  initialPage = 1,
  onClose,
}: {
  policyId: string;
  initialPage?: number;
  onClose: () => void;
}) {
  const [page, setPage] = useState(initialPage);
  const [imageFailed, setImageFailed] = useState(false);
  const [textOnly, setTextOnly] = useState(false);
  const policy = useQuery({
    queryKey: ["policy", policyId],
    queryFn: () => api.policy(policyId),
  });
  const content = useQuery({
    queryKey: ["page", policyId, page],
    queryFn: () => api.page(policyId, page),
  });
  return (
    <Modal
      title={policy.data?.filename || "Original document"}
      onClose={onClose}
      wide
    >
      <div className="viewer-toolbar">
        <div className="row-actions">
          <button
            className="icon-button"
            aria-label="Previous page"
            disabled={page === 1}
            onClick={() => {
              setPage(page - 1);
              setImageFailed(false);
            }}
          >
            <ChevronLeft size={19} />
          </button>
          <span>
            Page {page} of {content.data?.page_count ?? "…"}
          </span>
          <button
            className="icon-button"
            aria-label="Next page"
            disabled={!content.data || page >= content.data.page_count}
            onClick={() => {
              setPage(page + 1);
              setImageFailed(false);
            }}
          >
            <ChevronRight size={19} />
          </button>
        </div>
        <button className="text-button" onClick={() => setTextOnly(!textOnly)}>
          {textOnly ? "Show page" : "Read page text"}
        </button>
        {policy.data?.original_available && (
          <a
            className="button"
            href={`/api/policies/${encodeURIComponent(policyId)}/original`}
            download
          >
            <Download size={16} />
            Original PDF
          </a>
        )}
      </div>
      {content.isPending ? (
        <Loading />
      ) : content.error ? (
        <ErrorNotice error={content.error} retry={content.refetch} />
      ) : textOnly || !policy.data?.original_available || imageFailed ? (
        <div className="page-transcript">
          {imageFailed && (
            <div className="notice">
              The page image could not be loaded. The extracted text is shown
              below.
            </div>
          )}
          {!policy.data?.original_available && (
            <div className="notice">
              Illustrative excerpt. No original PDF is available.
            </div>
          )}
          <p>{content.data?.text || "No readable text on this page."}</p>
        </div>
      ) : (
        <img
          className="pdf-page"
          src={`/api/policies/${encodeURIComponent(policyId)}/pages/${page}/image`}
          alt={`Original policy, page ${page}. Use Read page text for an accessible transcript.`}
          onError={() => setImageFailed(true)}
        />
      )}
    </Modal>
  );
}
export function SourcePanel({
  source,
  onClose,
}: {
  source: Source;
  onClose: () => void;
}) {
  const [document, setDocument] = useState(false);
  const policy = useQuery({
    queryKey: ["policy", source.policy_id],
    queryFn: () => api.policy(source.policy_id),
  });
  return (
    <>
      <Modal title="From your policy" onClose={onClose}>
        <div className="source-document">
          <span className="eyebrow">SOURCE DOCUMENT</span>
          <h3>{policy.data?.filename || "Policy document"}</h3>
          <p>
            Page {source.page_start}
            {source.page_end !== source.page_start ? `–${source.page_end}` : ""}
            {source.section ? ` · ${source.section}` : ""}
          </p>
        </div>
        <blockquote className="source-excerpt">
          <Highlight text={source.text} quote={source.quote} />
        </blockquote>
        <Hint id="source">
          Read the surrounding wording too. Conditions on another page may
          affect what applies.
        </Hint>
        {policy.data?.original_available ? (
          <button className="button" onClick={() => setDocument(true)}>
            Open original page
            <ExternalLink size={16} />
          </button>
        ) : (
          <p className="meta">
            Original PDF unavailable. This is an excerpt only.
          </p>
        )}
      </Modal>
      {document && (
        <DocumentViewer
          policyId={source.policy_id}
          initialPage={source.page_start}
          onClose={() => setDocument(false)}
        />
      )}
    </>
  );
}
export function SourceButtons({
  sources,
  onSelect,
}: {
  sources: Source[];
  onSelect: (s: Source) => void;
}) {
  return (
    <div className="source-buttons">
      {sources.map((s) => (
        <button key={s.passage_id} onClick={() => onSelect(s)}>
          Page {s.page_start}
          {s.page_end !== s.page_start ? `–${s.page_end}` : ""}
          <ExternalLink size={12} />
        </button>
      ))}
    </div>
  );
}
