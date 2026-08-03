// Runs the browser classifier over a list of descriptions and prints what it
// decided, as JSON, one object per line.
//
// It exists so a Python test can hold the two implementations side by side.
// `classify.py` and `static/scripts/classify.js` evaluate the same trained
// model, and the moment they stop agreeing the offline suggestion becomes
// confidently different from the online one — which is worse than no offline
// suggestion at all, because nothing on screen would say so.
//
//     node tools/parity.mjs static/model/priority.json < descriptions.txt
//
// Reads one description per line, writes one result per line. Blank lines are
// preserved as empty input, because "what does it do with nothing" is a case
// worth agreeing about too.

import { readFile } from "node:fs/promises";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const modelPath = resolve(process.argv[2]
    || join(here, "..", "static", "model", "priority.json"));
const sourcePath = join(here, "..", "static", "scripts", "classify.js");

const model = JSON.parse(await readFile(modelPath, "utf8"));

// classify.js is an ES module, but a bare .js file in a directory with no
// package.json is read as CommonJS, where `export` is a syntax error. A data
// URL is always a module, needs no package.json and no scratch directory —
// which matters, because a temp dir is one more thing that can be full or
// read-only on whatever machine this runs on.
//
// It is the shipped file's own bytes, not a paraphrase of them.
const source = await readFile(sourcePath, "utf8");
const asModule = "data:text/javascript;base64,"
    + Buffer.from(source, "utf8").toString("base64");

// The module fetches its model. There is no server here, so hand it the file.
globalThis.fetch = async () => ({ ok: true, json: async () => model });

const { load, suggest } = await import(asModule);
if (!(await load())) {
    console.error(`parity: ${modelPath} is not a format this build understands`);
    process.exit(1);
}

const input = await new Promise((done) => {
    let buffer = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => { buffer += chunk; });
    process.stdin.on("end", () => done(buffer));
});

// A trailing newline is not a test case.
const lines = input.split("\n");
if (lines.length && lines[lines.length - 1] === "") lines.pop();

for (const line of lines) {
    process.stdout.write(JSON.stringify(suggest(line)) + "\n");
}
