import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { preparationProgress } from "./features/claims/rules";
import { startingGuide } from "./features/guide/content";
import { Hint, QuestionComposer } from "./shared/ui";
import { answerSchema } from "./api/contracts";
describe("product boundaries", () => {
  it("counts only known gathered items and complete details", () => {
    expect(preparationProgress("", "", [])).toBe(0);
    expect(preparationProgress("A stay", "2026-01-01", ["invoice"])).toBe(50);
    expect(
      preparationProgress("A stay", "2026-01-01", [
        "invoice",
        "invoice",
        "unknown",
      ]),
    ).toBe(50);
  });
  it("does not invent a country guide", () => {
    expect(startingGuide("BD", "no")).toBeNull();
    expect(startingGuide("US", "yes")?.url).toContain(
      "have-job-based-coverage",
    );
  });
  it("rejects unrecognized verification states", () => {
    expect(answerSchema.safeParse({ status: "probably_correct" }).success).toBe(
      false,
    );
  });
  it("submits literal question text and does not interpret HTML", () => {
    const send = vi.fn();
    render(<QuestionComposer onSubmit={send} />);
    fireEvent.change(screen.getByLabelText("Your policy question"), {
      target: { value: "<img src=x onerror=alert(1)>" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask question" }));
    expect(send).toHaveBeenCalledWith("<img src=x onerror=alert(1)>");
    expect(document.querySelector("img")).toBeNull();
  });
  it("dismisses contextual hints using only a preference", () => {
    localStorage.clear();
    render(<Hint id="source">Read the context</Hint>);
    fireEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(localStorage.getItem("policyiq:hint:source")).toBe("done");
    expect(screen.queryByText("Read the context")).not.toBeInTheDocument();
  });
});
