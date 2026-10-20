import { useState } from "react";
import { Link } from "react-router";
import { ArrowRight, ExternalLink, RotateCcw, Globe2 } from "lucide-react";
import { PageHeader, formatDate } from "../../shared/ui";
import { officialSources, reviewed, startingGuide } from "./content";
const hints = ["upload", "question", "source", "claim"];
export function GuidePage() {
  const [country, setCountry] = useState("");
  const [work, setWork] = useState("");
  const [result, setResult] = useState(false);
  const [status, setStatus] = useState("");
  const guide = startingGuide(country, work);
  return (
    <>
      <PageHeader
        eyebrow="HELP & GUIDE"
        title="Find a useful place to start."
        description="Optional guidance, whether you have a policy or are looking for one."
      />
      <div className="guide-layout">
        <section className="panel country-guide">
          {!result ? (
            <>
              <div className="guide-intro-icon">
                <Globe2 size={26} strokeWidth={1.4} />
              </div>
              <h2>Where do you currently live?</h2>
              <p className="section-intro">
                We will show a starting point where reviewed guidance is
                available.
              </p>
              <form
                className="form-stack"
                onSubmit={(e) => {
                  e.preventDefault();
                  setResult(true);
                }}
              >
                <div>
                  <label htmlFor="country">Country</label>
                  <select
                    id="country"
                    required
                    value={country}
                    onChange={(e) => {
                      setCountry(e.target.value);
                      setWork("");
                      setResult(false);
                    }}
                  >
                    <option value="">Choose a country</option>
                    <option value="BD">Bangladesh</option>
                    <option value="US">United States</option>
                    <option value="GB">United Kingdom</option>
                    <option value="other">Another country</option>
                  </select>
                </div>
                {country === "US" && (
                  <fieldset>
                    <legend>
                      Do you have coverage, or an offer, through a job?
                    </legend>
                    <label className="radio-row">
                      <input
                        type="radio"
                        name="job"
                        value="yes"
                        required
                        checked={work === "yes"}
                        onChange={() => setWork("yes")}
                      />
                      Yes
                    </label>
                    <label className="radio-row">
                      <input
                        type="radio"
                        name="job"
                        value="no"
                        checked={work === "no"}
                        onChange={() => setWork("no")}
                      />
                      No or I am not sure
                    </label>
                  </fieldset>
                )}
                <button className="button primary">
                  Find my starting point
                  <ArrowRight size={17} />
                </button>
              </form>
              <Link className="quiet-skip" to="/policies">
                Skip for now and go to My Policies
              </Link>
            </>
          ) : guide ? (
            <>
              <span className="eyebrow">UNITED STATES · STARTING GUIDE</span>
              <h2>{guide.title}</h2>
              <p className="section-intro">{guide.description}</p>
              <a
                className="button primary guide-primary"
                href={guide.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {guide.action}
                <ExternalLink size={17} />
              </a>
              <ol className="guide-steps">
                {guide.steps.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ol>
              <div className="notice">
                This guide does not determine eligibility, financial help, or
                enrollment dates. Check current requirements with the official
                service.
              </div>
              <details>
                <summary>Official sources & review date</summary>
                <ul className="official-sources">
                  {officialSources.map((s) => (
                    <li key={s.url}>
                      <a href={s.url} target="_blank" rel="noopener noreferrer">
                        {s.title}
                        <ExternalLink size={13} />
                      </a>
                    </li>
                  ))}
                </ul>
                <p className="meta">
                  Last reviewed {formatDate(reviewed)}. Review again when using
                  this guide.
                </p>
              </details>
              <div className="guide-result-actions">
                <button
                  className="text-button"
                  onClick={() => {
                    setResult(false);
                    setWork("");
                  }}
                >
                  Change country
                </button>
                <Link className="button" to="/policies">
                  Go to My Policies
                  <ArrowRight size={17} />
                </Link>
              </div>
            </>
          ) : (
            <>
              <span className="eyebrow">GUIDANCE NOT YET AVAILABLE</span>
              <h2>We do not have a reviewed guide for this country.</h2>
              <p className="section-intro">
                Use your insurer, employer benefits team, or local public health
                authority as a starting point. We cannot establish your
                eligibility from your country alone.
              </p>
              <div className="guide-result-actions">
                <button
                  className="text-button"
                  onClick={() => {
                    setResult(false);
                    setCountry("");
                    setWork("");
                  }}
                >
                  Change country
                </button>
                <Link className="button primary" to="/policies">
                  My Policies
                  <ArrowRight size={17} />
                </Link>
              </div>
            </>
          )}
        </section>
        <aside className="guide-side" aria-label="First-use assistance">
          <h2>A little help, when you need it</h2>
          <p>
            Short hints appear alongside uploads, questions, sources, and claim
            checklists.
          </p>
          <button
            className="button"
            onClick={() => {
              hints.forEach((id) =>
                localStorage.removeItem(`policyiq:hint:${id}`),
              );
              setStatus(
                "Hints are ready to appear again on the relevant screens.",
              );
            }}
          >
            <RotateCcw size={16} />
            Replay helpful hints
          </button>
          <button
            className="text-button"
            onClick={() => {
              hints.forEach((id) =>
                localStorage.setItem(`policyiq:hint:${id}`, "done"),
              );
              setStatus(
                "Hints dismissed. You can replay them here at any time.",
              );
            }}
          >
            Dismiss all hints
          </button>
          {status && (
            <p className="hint-status" role="status">
              {status}
            </p>
          )}
          <div className="divider" />
          <h3>Already have a policy?</h3>
          <p>You can start with your PDF and come back to this guide later.</p>
          <Link className="text-button" to="/policies">
            Open My Policies
          </Link>
        </aside>
      </div>
      <section className="guide-faq">
        <details>
          <summary>What does “Evidence verified” mean?</summary>
          <p>
            Each displayed claim passed citation checks and independent model
            verification against the retrieved passages. It does not guarantee
            correctness or an insurer's coverage decision. Conditions or
            unreadable pages can still matter.
          </p>
        </details>
        <details>
          <summary>Can I use a scanned policy?</summary>
          <p>
            Image-only PDFs need OCR before upload. This workspace does not
            perform OCR. Upload a searchable PDF and check any document
            warnings.
          </p>
        </details>
        <details>
          <summary>Does PolicyIQ submit a claim for me?</summary>
          <p>
            No. Claim Preparation organizes your details and a general
            checklist. You submit the actual claim through your insurer's
            process.
          </p>
        </details>
      </section>
    </>
  );
}
