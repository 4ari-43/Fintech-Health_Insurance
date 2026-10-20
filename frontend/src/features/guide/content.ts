export const reviewed = "2026-10-20";
export const officialSources = [
  {
    title: "Marketplace quick guide",
    url: "https://www.healthcare.gov/quick-guide/",
  },
  {
    title: "Coverage through a job",
    url: "https://www.healthcare.gov/have-job-based-coverage/",
  },
  {
    title: "Find your state Marketplace",
    url: "https://www.healthcare.gov/marketplace-in-your-state/",
  },
];
export function startingGuide(country: string, workCoverage: string) {
  if (country !== "US") return null;
  const employer = workCoverage === "yes";
  return {
    title: employer
      ? "Start with your job-based coverage options."
      : "Find the Marketplace for your state.",
    action: employer
      ? "Read the official job-based coverage guide"
      : "Find your state Marketplace",
    url: officialSources[employer ? 1 : 2].url,
    description: employer
      ? "An employer offer can affect Marketplace options and financial help. Read the official guidance before making a change."
      : "Use the official state directory to find where to begin your application.",
    steps: employer
      ? [
          "Gather your employer plan information before comparing options.",
          "Check the official Marketplace guide for current enrollment information.",
        ]
      : [
          "Read the official guide to understand enrollment and application options.",
          "Have your current coverage information ready when reviewing your options.",
        ],
  };
}
