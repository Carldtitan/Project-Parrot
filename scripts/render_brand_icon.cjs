const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");
const { createAppIconSvg } = require("../desktop/brand");

async function main() {
  const outputPath = path.resolve(process.argv[2] || ".build/icon.png");
  const size = Number.parseInt(process.argv[3] || "256", 10);
  if (!Number.isInteger(size) || size < 16 || size > 2048) {
    throw new Error("Icon size must be an integer between 16 and 2048.");
  }

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: size, height: size },
    deviceScaleFactor: 1,
  });
  const document = [
    "<!doctype html><html><head><meta charset=\"utf-8\">",
    "<style>html,body{width:100%;height:100%;margin:0;overflow:hidden;background:transparent}svg{display:block;width:100%;height:100%}</style>",
    "</head><body>",
    createAppIconSvg(size),
    "</body></html>",
  ].join("");
  await page.setContent(document);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  await page.screenshot({ path: outputPath, omitBackground: true });
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
