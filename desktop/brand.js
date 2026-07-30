const fs = require("node:fs");
const path = require("node:path");

const MARK_PATH = path.join(__dirname, "assets", "brand", "parrot-mark.svg");

function readMarkSvg() {
  return fs.readFileSync(MARK_PATH, "utf8");
}

function markBody(markSvg = readMarkSvg()) {
  return markSvg
    .replace(/<\?xml[^>]*>/g, "")
    .replace(/<title[\s\S]*?<\/title>/g, "")
    .replace(/^.*?<svg[^>]*>/s, "")
    .replace(/<\/svg>\s*$/s, "");
}

function createAppIconSvg(size = 256, { optical = false } = {}) {
  const inset = optical ? 0 : Math.round(size * 0.105);
  const innerSize = size - inset * 2;
  const radius = Math.round(size * 0.225);
  const markViewBox = optical ? "13 2 48 62" : "0 0 64 64";

  return [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">`,
    `<rect width="${size}" height="${size}" rx="${radius}" fill="#F1F6E8"/>`,
    `<svg x="${inset}" y="${inset}" width="${innerSize}" height="${innerSize}" viewBox="${markViewBox}">`,
    markBody(),
    "</svg>",
    "</svg>",
  ].join("");
}

module.exports = {
  MARK_PATH,
  createAppIconSvg,
  readMarkSvg,
};
