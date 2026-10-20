import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router";
import { MessageSquare, Plus, ArrowRight } from "lucide-react";
import { api, isDemo } from "../../api";
import type { Source, Conversation } from "../../api/contracts";
import { queryClient, usePolicies, useSelection } from "../../app/state";
import {
  PageHeader,
  ErrorNotice,
  Loading,
  QuestionComposer,
  Hint,
} from "../../shared/ui";
import { SourcePanel, SourceButtons } from "./Sources";
export function AskPage() {
  const policies = usePolicies();
  const { selected, select } = useSelection();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const id =
    params.get("policy") ||
    selected ||
    policies.data?.find((p) => !p.archived)?.id ||
    "";
  return (
    <>
      <PageHeader
        eyebrow="ASK POLICY"
        title="A question. A clearer next step."
        description="Understand the wording, with the sources beside it."
      />
      {policies.isPending ? (
        <Loading />
      ) : policies.error ? (
        <ErrorNotice error={policies.error} retry={policies.refetch} />
      ) : !policies.data?.length ? (
        <div className="empty-small">
          <MessageSquare size={30} />
          <h2>Add a policy to start asking</h2>
          <p>Your answers will refer to the document you choose.</p>
          <Link className="button primary" to="/policies">
            Add your policy
            <ArrowRight size={17} />
          </Link>
        </div>
      ) : (
        <>
          <div className="policy-selector">
            <label htmlFor="ask-policy">Policy</label>
            <select
              id="ask-policy"
              value={id}
              onChange={(e) => {
                select(e.target.value);
                navigate(`/ask?policy=${e.target.value}`, {
                  replace: true,
                  state: null,
                });
              }}
            >
              {policies.data.map((p) => (
                <option value={p.id} key={p.id}>
                  {p.filename}
                  {p.archived ? " (archived)" : ""}
                </option>
              ))}
            </select>
            <Link className="text-button" to={`/policies/${id}`}>
              Overview
            </Link>
          </div>
          <ConversationWorkspace key={id} id={id} />
        </>
      )}
    </>
  );
}
function ConversationWorkspace({ id }: { id: string }) {
  const location = useLocation();
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const [params, setParams] = useSearchParams();
  const [active, setActive] = useState(params.get("conversation") || "");
  const [source, setSource] = useState<Source>();
  const [initial, setInitial] = useState<string>(
    location.state?.question || "",
  );
  const [composerKey, setComposerKey] = useState(0);
  const [lastQuestion, setLastQuestion] = useState("");
  const conversations = useQuery({
    queryKey: ["conversations", id],
    queryFn: () => api.conversations(id),
  });
  const config = useQuery({ queryKey: ["config"], queryFn: api.config });
  const current = conversations.data?.find((c) => c.id === active);
  const ask = useMutation({
    mutationFn: (question: string) =>
      api.ask(id, question, active || undefined),
    onSuccess: (c: Conversation) => {
      if (!mounted.current) return;
      queryClient.setQueryData<Conversation[]>(["conversations", id], (old) => [
        c,
        ...(old || []).filter((x) => x.id !== c.id),
      ]);
      setActive(c.id);
      setParams({ policy: id, conversation: c.id }, { replace: true });
      setInitial("");
      setComposerKey((k) => k + 1);
    },
  });
  function send(question: string) {
    setLastQuestion(question);
    ask.mutate(question);
  }
  function fresh() {
    setActive("");
    setParams({ policy: id }, { replace: true });
    setInitial("");
    setComposerKey((k) => k + 1);
    ask.reset();
  }
  return (
    <>
      <div className="conversation-toolbar">
        <div>
          {conversations.data && conversations.data.length > 0 && (
            <>
              <label className="sr-only" htmlFor="conversation">
                Conversation history
              </label>
              <select
                id="conversation"
                disabled={ask.isPending}
                value={active}
                onChange={(e) => {
                  setActive(e.target.value);
                  setParams(
                    { policy: id, conversation: e.target.value },
                    { replace: true },
                  );
                  ask.reset();
                }}
              >
                <option value="">New conversation</option>
                {conversations.data.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </>
          )}
        </div>
        <button
          className="text-button"
          onClick={fresh}
          disabled={ask.isPending}
        >
          <Plus size={15} />
          New conversation
        </button>
      </div>
      {config.data && !config.data.questions_enabled && (
        <div className="notice">
          {config.data.processing} Questions need configured answer and
          verification providers.
        </div>
      )}
      {conversations.isPending ? (
        <Loading text="Loading conversation…" />
      ) : conversations.error ? (
        <ErrorNotice
          error={conversations.error}
          retry={conversations.refetch}
        />
      ) : (
        <div className="conversation-messages">
          {!current?.messages.length ? (
            <div className="question-empty">
              <div className="eyebrow">BEGIN WITH WHAT MATTERS</div>
              <h2>What would you like to understand?</h2>
              <div className="suggestions">
                {[
                  "What should I know before a hospital stay?",
                  "What does this policy exclude?",
                  "What are my out-of-pocket costs?",
                ].map((q) => (
                  <button
                    key={q}
                    onClick={() => {
                      setInitial(q);
                      setComposerKey((k) => k + 1);
                    }}
                  >
                    {q}
                    <ArrowRight size={16} />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            current.messages.map((m) => (
              <article className="message-pair" key={m.id}>
                <div className="user-question">
                  <span>YOU ASKED</span>
                  <p>{m.question}</p>
                </div>
                <div className="answer">
                  <div className="answer-heading">
                    <strong>PolicyIQ</strong>
                    <span
                      className={`badge ${m.answer.status === "verified" ? "" : "warning"}`}
                    >
                      {m.answer.status === "verified"
                        ? "Evidence verified"
                        : isDemo
                          ? "Illustrative response"
                          : "Not established"}
                    </span>
                  </div>
                  <p className="answer-direct">{m.answer.text}</p>
                  {m.answer.status === "verified" &&
                    m.answer.claims.length > 1 && (
                      <div className="answer-conditions">
                        <h3>Also applies</h3>
                        {m.answer.claims.slice(1).map((c, i) => (
                          <div key={i}>
                            <p>{c.text}</p>
                            <SourceButtons
                              sources={c.sources}
                              onSelect={setSource}
                            />
                          </div>
                        ))}
                      </div>
                    )}
                  <SourceButtons
                    sources={m.answer.sources}
                    onSelect={setSource}
                  />
                  {m.answer.missing_information.length > 0 && (
                    <div className="notice">
                      <div>
                        <strong>More information is needed</strong>
                        <ul>
                          {m.answer.missing_information.map((x) => (
                            <li key={x}>{x}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}
                  {m.answer.warnings.length > 0 && (
                    <details>
                      <summary>Limitations & document notes</summary>
                      {m.answer.warnings.map((w) => (
                        <p key={w}>{w}</p>
                      ))}
                    </details>
                  )}
                </div>
              </article>
            ))
          )}
        </div>
      )}
      {ask.isPending && (
        <Loading text="Finding evidence and independently checking the answer…" />
      )}
      {ask.error && (
        <ErrorNotice error={ask.error} retry={() => send(lastQuestion)} />
      )}
      <div className="sticky-composer">
        <QuestionComposer
          key={composerKey}
          initial={initial}
          onSubmit={send}
          pending={ask.isPending}
          compact
        />
        <Hint id="question">
          Add relevant details in a follow-up. Each answer is checked against
          this policy.
        </Hint>
      </div>
      {source && (
        <SourcePanel source={source} onClose={() => setSource(undefined)} />
      )}
    </>
  );
}
