import { useRef, useState } from "react";
import { useNavigate } from "react-router";
import { FileText, UploadCloud, X, ArrowRight } from "lucide-react";
import { api, isDemo } from "../../api";
import { queryClient, useSelection } from "../../app/state";
import { ErrorNotice, Hint } from "../../shared/ui";
export function UploadPanel({
  onDone,
  large = false,
}: {
  onDone?: () => void;
  large?: boolean;
}) {
  const [file, setFile] = useState<File>();
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<number>();
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const controller = useRef<AbortController | null>(null);
  const navigate = useNavigate();
  const { select } = useSelection();
  function choose(value?: File) {
    setError(undefined);
    setProgress(undefined);
    if (!value) return;
    if (!value.name.toLowerCase().endsWith(".pdf")) {
      setError(
        new Error("Choose a PDF file. Other file types are not supported."),
      );
      return;
    }
    if (value.size > 20 * 1024 * 1024) {
      setError(new Error("This file is too large. Choose a PDF up to 20 MB."));
      return;
    }
    if (!value.size) {
      setError(new Error("This file is empty. Choose another PDF."));
      return;
    }
    setFile(value);
  }
  async function submit() {
    if (!file) return;
    setBusy(true);
    setError(undefined);
    controller.current = new AbortController();
    try {
      const policy = await api.upload(
        file,
        controller.current.signal,
        setProgress,
      );
      select(policy.id);
      await queryClient.invalidateQueries({ queryKey: ["policies"] });
      onDone?.();
      navigate(`/policies/${policy.id}`);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <div
        className={`upload-zone ${large ? "large" : ""} ${drag ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (!busy) choose(e.dataTransfer.files[0]);
        }}
      >
        <input
          ref={input}
          type="file"
          className="sr-only"
          accept=".pdf,application/pdf"
          aria-label="Choose policy PDF"
          tabIndex={-1}
          onChange={(e) => choose(e.target.files?.[0])}
        />
        {file ? (
          <>
            <div className="file-symbol small">
              <FileText size={30} strokeWidth={1.3} />
            </div>
            <h2 className="file-name">{file.name}</h2>
            <p>{(file.size / 1024 / 1024).toFixed(2)} MB · PDF document</p>
            <div className="row-actions">
              <button
                className="button primary"
                disabled={busy}
                onClick={submit}
              >
                {busy ? "Processing document…" : "Upload policy"}
                {!busy && <ArrowRight size={17} />}
              </button>
              <button
                className="text-button"
                disabled={busy}
                onClick={() => input.current?.click()}
              >
                Replace
              </button>
              <button
                className="icon-button"
                disabled={busy}
                aria-label="Remove selected file"
                onClick={() => {
                  setFile(undefined);
                  setError(undefined);
                  if (input.current) input.current.value = "";
                }}
              >
                <X size={18} />
              </button>
            </div>
            {busy && (
              <div role="status">
                {progress === undefined
                  ? "Starting upload…"
                  : progress < 100
                    ? `Uploading ${progress}%`
                    : "Upload received. Reading your document…"}
                <button
                  className="text-button cancel-upload"
                  onClick={() => controller.current?.abort()}
                >
                  Cancel request
                </button>
              </div>
            )}
          </>
        ) : (
          <>
            <div className="file-symbol">
              <FileText size={44} strokeWidth={1.2} />
              <span className="document-rule" />
              <span className="document-rule short" />
            </div>
            <h2>Drop your policy here</h2>
            <p>Or choose a file from your device.</p>
            <button
              className="button primary"
              onClick={() => input.current?.click()}
            >
              <UploadCloud size={18} />
              Choose PDF
            </button>
            <span className="upload-requirements">
              PDF · Up to 20 MB · 300 pages · Searchable text
            </span>
          </>
        )}
      </div>
      {!!error && (
        <ErrorNotice error={error} retry={file && !busy ? submit : undefined} />
      )}
      {isDemo && (
        <p className="meta upload-note">
          Demo mode does not upload files. Use a fictional sample to explore.
        </p>
      )}
      <Hint id="upload">
        A searchable PDF lets us connect answers to the exact pages. You can
        remove it later.
      </Hint>
    </div>
  );
}
