const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { _electron: electron } = require("playwright");

const projectRoot = path.resolve(__dirname, "..");
const outputDirectory = path.resolve(
  process.argv[2] || ".impeccable/review/literal-parrot",
);

async function findWindow(app, title) {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    for (const window of app.windows()) {
      if ((await window.title()) === title) return window;
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error(`Window did not open: ${title}`);
}

async function sizeWindow(app, width, height) {
  await app.evaluate(
    ({ BrowserWindow }, bounds) => {
      const window = BrowserWindow.getAllWindows().find(
        (candidate) => candidate.getTitle() === "Parrot",
      );
      window.setSize(bounds.width, bounds.height);
      window.show();
      window.focus();
    },
    { width, height },
  );
}

async function main() {
  fs.mkdirSync(outputDirectory, { recursive: true });
  const userDataDirectory = fs.mkdtempSync(
    path.join(os.tmpdir(), "parrot-brand-review-"),
  );
  const packagedExecutable = process.env.PARROT_EXECUTABLE;
  const app = await electron.launch({
    executablePath: packagedExecutable || require("electron"),
    args: [
      ...(packagedExecutable ? [] : ["."]),
      "--ui-only",
      "--e2e",
      `--user-data-dir=${userDataDirectory}`,
    ],
    cwd: projectRoot,
  });

  try {
    const window = await findWindow(app, "Parrot");
    await window.waitForLoadState("domcontentloaded");
    const now = new Date().toISOString();
    await window.evaluate(
      async (createdAt) =>
        window.parrot.e2eSeed({
          history: [
            {
              id: "brand-one",
              text: "Ship the new parrot identity with the Windows release.",
              createdAt,
              durationSeconds: 7,
              wordCount: 10,
              source: "dictation",
            },
            {
              id: "brand-two",
              text: "Add a regression test for live transcription.",
              createdAt,
              durationSeconds: 5,
              wordCount: 8,
              source: "developer",
            },
          ],
          dictionary: [{ spoken: "project parrot", written: "Project Parrot" }],
          snippets: [],
          learnedWords: [{ key: "parrot", written: "Parrot", count: 4 }],
          recoveryDraft: "",
        }),
      now,
    );

    await sizeWindow(app, 1080, 760);
    await window.screenshot({
      path: path.join(outputDirectory, "home-1080.png"),
    });

    await sizeWindow(app, 760, 600);
    await window.screenshot({
      path: path.join(outputDirectory, "home-760.png"),
    });

    await window.locator("#hands-free-button").click();
    await window.waitForFunction(
      () => document.body.dataset.state === "recording",
    );
    await window.screenshot({
      path: path.join(outputDirectory, "recording-760.png"),
    });
    const overlay = await findWindow(app, "Parrot status");
    await overlay.screenshot({
      path: path.join(outputDirectory, "overlay-recording.png"),
    });
    await window.locator("#cancel-button").click();
    await window.waitForFunction(() => document.body.dataset.state === "ready");

    await window.getByRole("button", { name: "Settings" }).click();
    await window.mouse.move(500, 80);
    await window.screenshot({
      path: path.join(outputDirectory, "settings-760.png"),
    });
  } finally {
    await app.close().catch(() => {});
    fs.rmSync(userDataDirectory, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
