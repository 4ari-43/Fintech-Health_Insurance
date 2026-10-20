import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.use({ baseURL: "http://127.0.0.1:5176" });
const password = "Fictional-browser-password-123";
export function pdf(text: string) {
  const escaped = text.replace(/[\\()]/g, "\\$&");
  const stream = `BT /F1 12 Tf 45 750 Td (${escaped}) Tj ET`;
  const bodies = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
  ];
  let out = "%PDF-1.4\n";
  const offsets = [0];
  bodies.forEach((b, i) => {
    offsets.push(out.length);
    out += `${i + 1} 0 obj\n${b}\nendobj\n`;
  });
  const start = out.length;
  out += `xref\n0 6\n0000000000 65535 f \n${offsets
    .slice(1)
    .map((n) => String(n).padStart(10, "0") + " 00000 n ")
    .join(
      "\n",
    )}\ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${start}\n%%EOF`;
  return Buffer.from(out);
}
const policyText =
  "Fictional policy. The individual in-network annual deductible is $750. Prior authorization is required for planned admissions. Emergency services are covered. Cosmetic procedures are excluded.";
async function signup(page: Page) {
  const email = `browser-${crypto.randomUUID()}@example.test`;
  await page.goto("/signup");
  await page.getByLabel("Name", { exact: true }).fill("Alex Fiction");
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Start with your policy." }),
  ).toBeVisible();
  return email;
}
async function upload(
  page: Page,
  name = "Cedar Health - Essential.pdf",
  text = policyText,
) {
  await page
    .getByLabel("Choose policy PDF")
    .setInputFiles({ name, mimeType: "application/pdf", buffer: pdf(text) });
  await page
    .locator(".upload-zone")
    .getByRole("button", { name: "Upload policy", exact: true })
    .click();
  await expect(page).toHaveURL(/\/policies\/[a-f0-9]+$/);
  return page.url().split("/").pop()!;
}
async function assertNoOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
}

test("real signup, documents, question retry/sources/follow-up, claims, comparison, guide and logout", async ({
  page,
}, info) => {
  test.setTimeout(120000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  const email = await signup(page);
  await page.screenshot({
    path: info.outputPath("01-first-use-desktop.png"),
    fullPage: true,
  });
  const pid = await upload(page);
  await page.screenshot({
    path: info.outputPath("02-policy-overview.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "View document", exact: true })
    .click();
  await expect(page.locator("img.pdf-page")).toBeVisible();
  await page.getByRole("button", { name: "Read page text" }).click();
  await expect(page.locator(".page-transcript")).toContainText("$750");
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "View document", exact: true }),
  ).toBeFocused();
  let calls = 0;
  const messages: unknown[] = [];
  await page.route("**/api/config", (route) =>
    route.fulfill({
      json: {
        questions_enabled: true,
        processing: "Controlled browser-test model mock.",
        reset_delivery: "Not configured",
      },
    }),
  );
  await page.route("**/api/policies/*/questions", async (route) => {
    calls++;
    if (calls === 1) {
      await route.fulfill({
        status: 503,
        json: { detail: "Controlled verifier failure. Please retry." },
      });
      return;
    }
    const body = route.request().postDataJSON();
    const source = {
      policy_id: pid,
      passage_id: pid + "_c1",
      page_start: 1,
      page_end: 1,
      section: "Fictional benefits",
      text: policyText,
      quote: "The individual in-network annual deductible is $750.",
    };
    messages.push({
      id: crypto.randomUUID(),
      question: body.question,
      created_at: new Date().toISOString(),
      answer: {
        status: "verified",
        text: "The individual in-network annual deductible is $750.",
        claims: [
          {
            text: "The individual in-network annual deductible is $750.",
            sources: [source],
          },
        ],
        sources: [source],
        warnings: [],
        missing_information: [],
      },
    });
    await route.fulfill({
      json: {
        id: "controlled-conversation",
        policy_id: pid,
        title: "Deductible",
        messages,
      },
    });
  });
  await page.getByLabel("Your policy question").fill("What is my deductible?");
  await page.getByRole("button", { name: "Ask question", exact: true }).click();
  await page.getByRole("button", { name: "Ask question", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Controlled verifier failure",
  );
  await expect(
    page.getByText("Evidence verified", { exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(
    page.getByText("Evidence verified", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Page 1", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "From your policy" }),
  ).toBeVisible();
  await expect(page.locator("mark")).toHaveText(
    "The individual in-network annual deductible is $750.",
  );
  await page.screenshot({
    path: info.outputPath("03-source-panel.png"),
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Page 1", exact: true }),
  ).toBeFocused();
  await page
    .getByLabel("Your policy question")
    .fill("What about an out-of-network provider?");
  await page.getByRole("button", { name: "Ask question", exact: true }).click();
  await expect(page.locator(".message-pair")).toHaveCount(2);
  await page.goto(`/claims?policy=${pid}`);
  await page
    .getByLabel("Brief incident description")
    .fill('Fictional overnight hospital stay <script>alert("unsafe")</script>');
  await page.getByLabel("Incident date").fill("2026-01-10");
  await page.getByRole("button", { name: "Continue to documents" }).click();
  await expect(
    page.getByRole("heading", { name: "Gather your documents" }),
  ).toBeVisible();
  await page.getByRole("checkbox", { name: /Itemized bill/ }).check();
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "50");
  await page.getByRole("button", { name: "Back", exact: true }).click();
  await expect(page.getByLabel("Brief incident description")).toHaveValue(
    /Fictional overnight/,
  );
  await page.getByRole("button", { name: "Continue to documents" }).click();
  await expect(
    page.getByRole("checkbox", { name: /Itemized bill/ }),
  ).toBeChecked();
  await page.getByRole("button", { name: "Review summary" }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export summary" }).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  let exported = "";
  for await (const chunk of stream!) exported += chunk.toString();
  expect(exported).toContain('<script>alert("unsafe")</script>');
  expect(exported).toContain("Not submitted");
  await page.screenshot({
    path: info.outputPath("04-claim-review.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Save & close" }).click();
  await expect(page.getByText("Saved draft", { exact: true })).toBeVisible();
  await page.goto("/policies");
  await page
    .getByRole("button", { name: "Upload policy", exact: true })
    .click();
  await upload(
    page,
    "Harbor Health - Plus.pdf",
    "Fictional second policy. The annual individual deductible is $1000. Emergency care is covered. Out-of-network care requires review.",
  );
  await page.goto("/compare");
  await page.getByLabel("First policy").selectOption(pid);
  const options = await page
    .getByLabel("Second policy")
    .locator("option")
    .evaluateAll((els) => els.map((e) => (e as HTMLOptionElement).value));
  await page
    .getByLabel("Second policy")
    .selectOption(options.find((x) => x && x !== pid)!);
  await page
    .getByRole("button", { name: "Compare policies", exact: true })
    .click();
  await expect(page.locator(".comparison-row")).toHaveCount(9);
  await page.locator(".source-buttons button").first().click();
  await expect(
    page.getByRole("dialog", { name: "From your policy" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await page.screenshot({
    path: info.outputPath("05-comparison.png"),
    fullPage: true,
  });
  await page.goto("/guide");
  await page.getByLabel("Country", { exact: true }).selectOption("US");
  await page.getByRole("radio", { name: "No or I am not sure" }).check();
  await page.getByRole("button", { name: "Find my starting point" }).click();
  await expect(
    page.getByRole("heading", { name: "Find the Marketplace for your state." }),
  ).toBeVisible();
  await page
    .getByText("Official sources & review date", { exact: true })
    .click();
  await expect(page.getByText(/Last reviewed/)).toContainText("2026");
  await page.getByRole("button", { name: "Change country" }).click();
  await page.getByLabel("Country", { exact: true }).selectOption("BD");
  await expect(page.getByRole("radio")).toHaveCount(0);
  await page.getByRole("button", { name: "Find my starting point" }).click();
  await expect(
    page.getByRole("heading", { name: /do not have a reviewed guide/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Dismiss all hints" }).click();
  await expect(page.getByRole("status")).toContainText("Hints dismissed");
  await page.getByRole("button", { name: "Replay helpful hints" }).click();
  await expect(page.getByRole("status")).toContainText("ready to appear again");
  await page.goto(`/policies/${pid}`);
  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: "Cedar Health - Essential",
      exact: true,
    }),
  ).toBeVisible();
  await page.goto("/settings");
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto(`/policies/${pid}`);
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Your policies, in one place." }),
  ).toBeVisible();
});

test("mobile upload failure recovery, keyboard modal and accessibility", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signup(page);
  await assertNoOverflow(page);
  await page.getByLabel("Choose policy PDF").setInputFiles({
    name: "invalid.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("invalid"),
  });
  await expect(page.getByRole("alert")).toContainText("Choose a PDF");
  await page.getByLabel("Choose policy PDF").setInputFiles({
    name: "corrupt.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.7 corrupted"),
  });
  await page
    .locator(".upload-zone")
    .getByRole("button", { name: "Upload policy", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("could not be read");
  await page.getByRole("button", { name: "Replace", exact: true }).click();
  await upload(page);
  await assertNoOverflow(page);
  await page.screenshot({
    path: info.outputPath("mobile-overview.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("dialog", { name: "Navigation" })).toBeVisible();
  await page.keyboard.press("Shift+Tab");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Open navigation" }),
  ).toBeFocused();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("late answers cannot cross policy selection; other users cannot open originals", async ({
  page,
  browser,
}) => {
  await signup(page);
  const first = await upload(page);
  await page.goto("/policies");
  await page
    .getByRole("button", { name: "Upload policy", exact: true })
    .click();
  const second = await upload(
    page,
    "Harbor Health - Plus.pdf",
    "Fictional second policy. The annual individual deductible is $1000.",
  );
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/policies/*/questions", async (route) => {
    await waiting;
    await route.fulfill({
      json: {
        id: "late",
        policy_id: first,
        title: "Late answer",
        messages: [
          {
            id: "late-message",
            question: "Old question",
            created_at: new Date().toISOString(),
            answer: {
              status: "insufficient_evidence",
              text: "OLD POLICY ANSWER",
              claims: [],
              sources: [],
              warnings: [],
              missing_information: [],
            },
          },
        ],
      },
    });
  });
  await page.goto(`/ask?policy=${first}`);
  await page.getByLabel("Your policy question").fill("What is my deductible?");
  await page.getByRole("button", { name: "Ask question", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Checking evidence…" }),
  ).toBeVisible();
  await page.getByLabel("Policy", { exact: true }).selectOption(second);
  release();
  await expect(page).toHaveURL(new RegExp(`policy=${second}`));
  await expect(page.getByText("OLD POLICY ANSWER")).toHaveCount(0);
  await expect(page.getByLabel("Policy", { exact: true })).toHaveValue(second);
  const other = await browser.newContext({ baseURL: "http://127.0.0.1:5176" });
  const otherPage = await other.newPage();
  await signup(otherPage);
  await otherPage.goto(`/policies/${first}`);
  await expect(otherPage.getByRole("alert")).toContainText("Policy not found");
  expect(
    (await other.request.get(`/api/policies/${first}/original`)).status(),
  ).toBe(404);
  await other.close();
  await page.context().clearCookies();
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText(/session has ended/)).toBeVisible();
});

test("all main screens fit 1024px and first-use guidance is optional", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 1024, height: 850 });
  await signup(page);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: "Got it", exact: true }).click();
  await page.goto("/guide");
  await page
    .getByRole("link", { name: "Skip for now and go to My Policies" })
    .click();
  await expect(
    page.getByRole("button", { name: "Got it", exact: true }),
  ).toHaveCount(0);
  await page.goto("/guide");
  await page.getByRole("button", { name: "Replay helpful hints" }).click();
  await page
    .getByRole("link", { name: "Skip for now and go to My Policies" })
    .click();
  await expect(
    page.getByRole("button", { name: "Got it", exact: true }),
  ).toBeVisible();
  const pid = await upload(page);
  for (const path of [
    `/policies/${pid}`,
    `/ask?policy=${pid}`,
    `/claims?policy=${pid}`,
    "/guide",
    "/settings",
  ]) {
    await page.goto(path);
    await expect(page.locator("main h1")).toBeVisible();
    await assertNoOverflow(page);
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  }
  await page.screenshot({
    path: info.outputPath("tablet-settings.png"),
    fullPage: true,
  });
});
