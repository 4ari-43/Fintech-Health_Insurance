import { test, expect } from "@playwright/test";
test("shared navigation and direct routes fit desktop and mobile", async ({
  page,
}) => {
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of [
      "/policies",
      "/ask",
      "/claims",
      "/guide",
      "/settings",
    ]) {
      await page.goto(route);
      await expect(page.locator("h1")).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      if (width > 760)
        await expect(page.locator(".sidebar nav").first()).toHaveText(
          /My PoliciesAsk PolicyClaim Preparation/,
        );
    }
  }
});
