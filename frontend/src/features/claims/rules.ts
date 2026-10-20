export const suggestedDocuments = [
  {
    id: "invoice",
    label: "Itemized bill or receipt",
    detail: "The services, charges, and any payments you made.",
  },
  {
    id: "treatment",
    label: "Treatment or discharge summary",
    detail: "A record of the care you received.",
  },
  {
    id: "policy",
    label: "Policy and member information",
    detail: "The policy details you will need when contacting your insurer.",
  },
];
export function preparationProgress(
  description: string,
  date: string,
  gathered: string[],
) {
  return Math.round(
    (((description.trim().length >= 3 && !!date ? 1 : 0) +
      suggestedDocuments.filter((d) => gathered.includes(d.id)).length) /
      4) *
      100,
  );
}
export function downloadText(filename: string, text: string) {
  const url = URL.createObjectURL(
    new Blob([text], { type: "text/plain;charset=utf-8" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
