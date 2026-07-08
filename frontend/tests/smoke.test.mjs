import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const readJson = async (path) => JSON.parse(await readFile(path, "utf8"));


test("package exposes required Next.js scripts", async () => {
  const packageJson = await readJson(new URL("../package.json", import.meta.url));

  assert.equal(packageJson.scripts.dev, "next dev -H 0.0.0.0 -p 3000");
  assert.equal(packageJson.scripts.build, "next build");
  assert.equal(packageJson.scripts.start, "next start -H 0.0.0.0 -p 3000");
});


test("home page is the dashboard skeleton", async () => {
  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  assert.match(page, /DispatchAI Staff Dashboard/);
  assert.match(page, /NEXT_PUBLIC_API_BASE_URL/);
});
