const assert = require("node:assert/strict");
const test = require("node:test");

const { createAppIconSvg, readMarkSvg } = require("./brand");

test("canonical mark is a compact literal parrot SVG", () => {
  const mark = readMarkSvg();
  assert.match(mark, /viewBox="0 0 64 64"/);
  assert.match(mark, /#123F35/);
  assert.match(mark, /#C7EE57/);
  assert.match(mark, /#FF7259/);
  assert.doesNotMatch(mark, /gradient|filter|font-family/i);
});

test("app icon wraps the canonical mark deterministically", () => {
  const first = createAppIconSvg(256);
  const second = createAppIconSvg(256);
  assert.equal(first, second);
  assert.match(first, /width="256" height="256"/);
  assert.match(first, /rx="58"/);
  assert.match(first, /viewBox="0 0 64 64"/);
});
