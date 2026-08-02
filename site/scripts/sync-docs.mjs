// Copies ../docs/*.md into src/pages and gives each one the frontmatter Astro
// needs to render it.
//
// The docs live at the repo root because that's where anyone reading the
// source will look for them. Copying at build time means there's exactly one
// copy to edit — the generated pages are gitignored, so nobody can edit the
// wrong one by accident.

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const docs = join(here, "..", "..", "docs");
const pages = join(here, "..", "src", "pages");

// slug -> [source file, title, one-line description]
const SITE = {
  architecture: ["architecture.md", "Architecture",
    "The data model, what runs on a request, and where each design gives out."],
  decisions: ["decisions.md", "Decisions",
    "What we chose, and what we gave up to choose it."],
  process: ["process.md", "Process",
    "What actually happened, including the parts that broke."],
  offline: ["offline.md", "Offline and LoRa",
    "The radio packet, the gateway, and a blunt table of what isn't built."],
  limits: ["limits.md", "Limits",
    "What this does not do. Written down rather than hoped over."],
  disclaimer: ["disclaimer.md", "Disclaimer",
    "It does not call for help, and the triage helper is not medical advice."],
  api: ["api.md", "API",
    "Every endpoint, what it takes, and what comes back."],
};

await mkdir(pages, { recursive: true });

for (const [slug, [file, title, description]] of Object.entries(SITE)) {
  const body = await readFile(join(docs, file), "utf8");

  // The source files start with their own H1. The layout renders the title,
  // so drop it rather than showing it twice.
  const withoutHeading = body.replace(/^#\s+.*\r?\n+/, "");

  const frontmatter = [
    "---",
    "layout: ../layouts/Doc.astro",
    `title: ${JSON.stringify(title)}`,
    `description: ${JSON.stringify(description)}`,
    "---",
    "",
  ].join("\n");

  await writeFile(join(pages, `${slug}.md`), frontmatter + withoutHeading);
  console.log(`synced ${file} -> /${slug}`);
}
