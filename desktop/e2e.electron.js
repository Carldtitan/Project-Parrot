const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { _electron: electron } = require("playwright");

const projectRoot = path.resolve(__dirname, "..");
const electronExecutable = require("electron");

async function mainWindow(app) {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    for (const window of app.windows()) {
      if ((await window.title()) === "Parrot") return window;
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error("Parrot main window did not open");
}

async function showMain(app) {
  await app.evaluate(({ BrowserWindow }) => {
    const window = BrowserWindow.getAllWindows().find(
      (candidate) => candidate.getTitle() === "Parrot",
    );
    window.setSize(960, 720);
    window.show();
    window.focus();
  });
}

test(
  "Parrot desktop workflow works end to end in preview mode",
  { timeout: 45000 },
  async (context) => {
    const userDataDirectory = fs.mkdtempSync(
      path.join(os.tmpdir(), "parrot-electron-e2e-"),
    );
    const app = await electron.launch({
      executablePath: electronExecutable,
      args: [
        ".",
        "--ui-only",
        "--e2e",
        `--user-data-dir=${userDataDirectory}`,
      ],
      cwd: projectRoot,
    });
    context.after(async () => {
      await app.close().catch(() => {});
      fs.rmSync(userDataDirectory, { recursive: true, force: true });
    });

    const window = await mainWindow(app);
    await window.waitForLoadState("domcontentloaded");
    await showMain(app);

    const now = new Date().toISOString();
    await window.evaluate(
      async (createdAt) =>
        window.parrot.e2eSeed({
          history: [
            {
              id: "history-one",
              text: "Refactor the authentication middleware and add a regression test.",
              createdAt,
              durationSeconds: 8,
              wordCount: 9,
              source: "developer",
            },
            {
              id: "history-two",
              text: "Send Maya the updated interview notes.",
              createdAt,
              durationSeconds: 5,
              wordCount: 6,
              source: "dictation",
            },
          ],
          dictionary: [
            { spoken: "cloud flare", written: "Cloudflare" },
          ],
          snippets: [
            {
              trigger: "release link",
              content:
                "https://github.com/Carldtitan/Project-Parrot/releases/download/latest/Parrot.exe",
            },
          ],
          learnedWords: [
            { key: "cloudflare", written: "Cloudflare", count: 3 },
          ],
          recoveryDraft: "",
        }),
      now,
    );

    assert.equal(await window.locator("#session-count").textContent(), "2");
    assert.equal(await window.locator("#recent-list .activity-row").count(), 2);

    await window.locator("#hands-free-button").click();
    await window.waitForFunction(
      () => document.body.dataset.state === "recording",
    );
    assert.equal(await window.locator("#cancel-button").isEnabled(), true);
    assert.equal(
      await app.evaluate(({ BrowserWindow }) => {
        const overlay = BrowserWindow.getAllWindows().find(
          (candidate) => candidate.getTitle() === "Parrot status",
        );
        return overlay.isVisible();
      }),
      true,
    );
    await window.locator("#cancel-button").click();
    await window.waitForFunction(() => document.body.dataset.state === "ready");

    await window.getByRole("button", { name: "History" }).click();
    assert.equal(await window.locator("#history-list .history-row").count(), 2);
    await window.locator("#history-search").fill("authentication");
    assert.equal(await window.locator("#history-list .history-row").count(), 1);
    await window.locator("#history-search").fill("");
    const firstHistoryRow = window.locator("#history-list .history-row").first();
    await firstHistoryRow.hover();
    await firstHistoryRow.getByRole("button", { name: "Copy" }).click();
    assert.match(
      await app.evaluate(({ clipboard }) => clipboard.readText()),
      /authentication middleware/,
    );

    await window.getByRole("button", { name: "Personalize" }).click();
    await window.locator("#dictionary-spoken").fill("open ai");
    await window.locator("#dictionary-written").fill("OpenAI");
    await window.getByRole("button", { name: "Add word" }).click();
    assert.equal(await window.locator("#dictionary-list .data-row").count(), 2);
    await window.locator("#snippet-trigger").fill("my email");
    await window.locator("#snippet-content").fill("carl@example.com");
    await window.getByRole("button", { name: "Add snippet" }).click();
    assert.equal(await window.locator("#snippet-list .data-row").count(), 2);

    await window.getByRole("button", { name: "Settings" }).click();
    assert.equal(
      await window.locator(
        "#push-to-talk-shortcut option[value='Mouse4']",
      ).count(),
      1,
    );
    await window.locator("#hands-free-shortcut").selectOption("F8");
    await window.locator("#cancel-shortcut").selectOption("F8");
    await window
      .locator("label.toggle-row")
      .filter({ hasText: "Remove filler words" })
      .click();
    await window.getByRole("button", { name: "Save and restart" }).click();
    const saved = await window.evaluate(() => window.parrot.getState());
    assert.equal(saved.settings.handsFreeShortcut, "F8");
    assert.equal(saved.settings.cancelShortcut, "Ctrl+Alt+Escape");
    assert.equal(saved.settings.cleanupFillers, false);

    await app.evaluate(({ BrowserWindow }) => {
      const main = BrowserWindow.getAllWindows().find(
        (candidate) => candidate.getTitle() === "Parrot",
      );
      main.setSize(760, 600);
      main.show();
    });
    const viewport = await window.evaluate(() => ({
      width: innerWidth,
      height: innerHeight,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      canScrollX:
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
      overflowers: [...document.querySelectorAll("*")]
        .map((element) => {
          const rect = element.getBoundingClientRect();
          return {
            tag: element.tagName,
            id: element.id,
            className:
              typeof element.className === "string" ? element.className : "",
            right: Math.round(rect.right),
            width: Math.round(rect.width),
          };
        })
        .filter((element) => element.right > innerWidth + 1)
        .slice(0, 12),
    }));
    assert.ok(viewport.width >= 760);
    assert.ok(viewport.height >= 600);
    assert.equal(viewport.canScrollX, false, JSON.stringify(viewport));
  },
);
