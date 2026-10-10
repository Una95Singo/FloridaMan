const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("fs");
(async () => {
  const opts = { headless: true };
  if (process.env.CHROMIUM_PATH) {
    opts.executablePath = process.env.CHROMIUM_PATH;
    opts.args = [
      "--no-sandbox",
      "--disable-dev-shm-usage",
      "--no-zygote",
      "--use-gl=angle",
      "--use-angle=swiftshader",
    ];
    opts.env = {
      ...process.env,
      LD_LIBRARY_PATH: process.env.CHROMIUM_LIBS || "",
    };
  }
  const b = await chromium.launch(opts),
    p = await b.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  p.on("pageerror", (e) => errors.push(e.message));
  const base = process.env.BASE_URL || "http://127.0.0.1:8000";
  const out = process.env.EVIDENCE_DIR || "test-evidence";
  fs.mkdirSync(out, { recursive: true });
  await p.goto(base);
  await p
    .getByRole("button", { name: "Review analysis", exact: true })
    .waitFor();
  await p.waitForTimeout(1200);
  await p.screenshot({ path: out + "/desktop-watch.png" });
  await p.getByRole("button", { name: "Map layers", exact: true }).click();
  await p
    .getByRole("checkbox", { name: "Previous advisory", exact: true })
    .check();
  await p.getByRole("button", { name: "Close layers", exact: true }).click();
  await p.getByRole("button", { name: "Review analysis", exact: true }).click();
  await p.getByRole("tab", { name: "Source", exact: true }).click();
  await p
    .getByText("Synthetic track comparison created", { exact: false })
    .waitFor();
  await p.screenshot({ path: out + "/desktop-evidence.png" });
  await p
    .getByRole("button", { name: "Open demo review", exact: true })
    .click();
  await p.getByRole("button", { name: "Correct", exact: true }).click();
  await p
    .getByLabel("What should change?", { exact: true })
    .fill("Explain that track proximity does not establish insured exposure.");
  await p
    .getByLabel("Why?", { exact: true })
    .fill("No insured exposure dataset supports a financial interpretation.");
  await p.getByRole("button", { name: "Save correction", exact: true }).click();
  await p
    .getByRole("button", { name: "Authorize replay & recheck", exact: true })
    .click();
  await p
    .getByRole("button", { name: "Review this version", exact: true })
    .click();
  if (
    !(await p
      .getByRole("button", { name: "Approve this version", exact: true })
      .isDisabled())
  )
    throw Error("acknowledgement guard failed");
  await p.getByLabel("I reviewed this version and its uncertainty.").check();
  await p
    .getByRole("button", { name: "Approve this version", exact: true })
    .click();
  await p
    .getByRole("button", { name: "Review operator release", exact: true })
    .click();
  await p
    .getByRole("button", { name: "Release approved version", exact: true })
    .click();
  await p
    .getByRole("button", { name: "Read the memo", exact: true })
    .first()
    .click();
  await p
    .locator(".memo-paper")
    .getByText("Review and version", { exact: false })
    .waitFor();
  const pdfUrl = await p
    .getByRole("link", { name: "Download PDF", exact: true })
    .getAttribute("href");
  const pdf = await p.request.get(base + pdfUrl);
  if (
    !pdf.ok() ||
    !(await pdf.body()).subarray(0, 4).equals(Buffer.from("%PDF"))
  )
    throw Error("PDF download failed");
  fs.writeFileSync(out + "/released-memo.pdf", await pdf.body());
  await p.screenshot({ path: out + "/desktop-memo.png" });
  await p.setViewportSize({ width: 390, height: 844 });
  await p.goto(base);
  await p
    .getByRole("button", { name: "Review analysis", exact: true })
    .waitFor();
  await p.waitForTimeout(500);
  await p.screenshot({ path: out + "/phone-watch.png" });
  if (await p.evaluate(() => document.documentElement.scrollWidth > innerWidth))
    throw Error("phone horizontal overflow");
  await p.getByRole("button", { name: "Review analysis", exact: true }).click();
  await p
    .getByRole("button", { name: "Inspect evidence", exact: true })
    .click();
  await p.screenshot({ path: out + "/phone-evidence.png" });
  await p
    .getByRole("button", { name: "Open expert review", exact: true })
    .click();
  await p.screenshot({ path: out + "/phone-review.png" });
  await p
    .getByRole("button", { name: "Decision history", exact: true })
    .click();
  await p.getByText("correct", { exact: true }).waitFor();
  await p.reload();
  await p.getByRole("button", { name: "Reviews", exact: true }).last().click();
  await p
    .getByRole("button", { name: "Open the release", exact: true })
    .waitFor();
  if (errors.length) throw Error(errors.join("\n"));
  fs.writeFileSync(
    out + "/browser-results.json",
    JSON.stringify(
      {
        status: "passed",
        scope: "Real FastAPI/SQLAlchemy isolated demo workflow",
        checks: [
          "responsive desktop and phone",
          "geographic fallback renders real land data",
          "advisory layer control",
          "versioned source inspection",
          "persistent correction",
          "operator-authorized replay and QC",
          "acknowledged expert approval",
          "separate operator release",
          "digest-bound PDF download",
          "audit record",
          "state survives reload",
        ],
        production_oidc: "not_run",
        live_analysis: "not_run",
      },
      null,
      2,
    ),
  );
  await b.close();
  console.log("Browser workflow passed.");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
