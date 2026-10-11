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
  const consoleErrors = [];
  p.on("pageerror", (e) => errors.push(e.message));
  p.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });
  const base = process.env.BASE_URL || "http://127.0.0.1:8000";
  const out = process.env.EVIDENCE_DIR || "test-evidence";
  fs.mkdirSync(out, { recursive: true });
  // On failure, record what the page showed so a CI log explains itself.
  process.on("unhandledRejection", async (e) => {
    try {
      const state = {
        failure: String(e && e.message ? e.message : e),
        url: p.url(),
        buttons: await p.getByRole("button").allInnerTexts(),
        page_errors: errors,
        console_errors: consoleErrors,
        panel_text: await p
          .locator(".reading-panel")
          .innerText()
          .catch(() => ""),
      };
      fs.writeFileSync(out + "/failure.json", JSON.stringify(state, null, 2));
      await p.screenshot({ path: out + "/failure.png", fullPage: true });
      console.error(JSON.stringify(state, null, 2));
    } catch (inner) {
      console.error("Could not capture failure state:", inner);
    }
    console.error(e);
    process.exit(1);
  });
  await p.goto(base);
  await p
    .getByRole("button", { name: "Review analysis", exact: true })
    .waitFor();
  await p.waitForTimeout(1200);
  await p.screenshot({ path: out + "/desktop-watch.png" });
  // Record which geography path actually rendered. The evidence must not
  // claim a GPU map when the SVG fallback drew the page, or the reverse.
  const mapPath = await p.evaluate(() =>
    document.querySelector(".geographic-fallback svg")
      ? "svg-fallback"
      : document.querySelector(".maplibregl-canvas")
        ? "maplibre-webgl"
        : "none",
  );
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
  // Interrupt the approval response once, after the server has processed the
  // request. The client must recover the saved operation by its idempotency
  // key instead of assuming failure or sending a second decision.
  let interrupted = false;
  await p.route("**/api/cases/*/actions", async (route) => {
    if (interrupted) return route.continue();
    interrupted = true;
    await route.fetch();
    await route.abort("failed");
  });
  await p
    .getByRole("button", { name: "Approve this version", exact: true })
    .click();
  await p.getByText("Approved. Waiting for operator release.").waitFor();
  await p.unroute("**/api/cases/*/actions");
  if (!interrupted) throw Error("approval response was not interrupted");
  const approvals = (
    await p.request.get(base + "/api/cases/demo-gulf/audit")
  )
    .json()
    .then((rows) => rows.filter((r) => r.action === "approve").length);
  if ((await approvals) !== 1)
    throw Error("expected exactly one recorded approval, got " + (await approvals));
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
  const viewports = [];
  for (const [width, height] of [
    [360, 740],
    [768, 1024],
    [1440, 900],
  ]) {
    await p.setViewportSize({ width, height });
    await p.goto(base);
    await p
      .getByRole("button", { name: "Review analysis", exact: true })
      .waitFor();
    await p.waitForTimeout(400);
    await p.screenshot({ path: out + `/watch-${width}x${height}.png` });
    const overflow = await p.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    );
    if (overflow) throw Error(`horizontal overflow at ${width}px`);
    viewports.push(`${width}x${height}`);
  }
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
        browser: b.version(),
        map_path: mapPath,
        viewports_without_horizontal_overflow: [...viewports, "390x844"],
        checks: [
          "responsive desktop and phone",
          mapPath === "svg-fallback"
            ? "geographic fallback renders real land data"
            : "MapLibre WebGL map renders real land data",
          "advisory layer control",
          "versioned source inspection",
          "persistent correction",
          "operator-authorized replay and QC",
          "acknowledged expert approval",
          "operation recovery after an interrupted response",
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
})();
