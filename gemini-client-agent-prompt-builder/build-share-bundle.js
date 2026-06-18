#!/usr/bin/env node
/*
 * Bundles the Gemini client-agent prompt builder into a single, self-contained
 * HTML file that can be shared and opened without any other files.
 *
 * It inlines gemini-client-agent-prompt-locales.js into
 * gemini-client-agent-prompt-builder.html and writes the result to
 * share/index.html.
 *
 * Re-run after editing the builder or the locales:
 *   node build-share-bundle.js
 */
const fs = require("fs");
const path = require("path");

const projectRoot = __dirname;

const htmlPath = path.join(projectRoot, "gemini-client-agent-prompt-builder.html");
const localesPath = path.join(projectRoot, "gemini-client-agent-prompt-locales.js");
const outDir = path.join(projectRoot, "share");
const outPath = path.join(outDir, "index.html");

const SCRIPT_TAG = '<script src="gemini-client-agent-prompt-locales.js"></script>';

function build() {
  const html = fs.readFileSync(htmlPath, "utf8");
  const locales = fs.readFileSync(localesPath, "utf8");

  if (!html.includes(SCRIPT_TAG)) {
    throw new Error(
      `Could not find the locales <script src> tag in the builder HTML.\n` +
        `Expected: ${SCRIPT_TAG}`
    );
  }

  // Guard against a literal </script> inside the JS breaking the inline tag.
  const safeLocales = locales.replace(/<\/script>/gi, "<\\/script>");
  const inlined = `<script>\n/* Inlined from gemini-client-agent-prompt-locales.js */\n${safeLocales}\n</script>`;

  const bundled = html.replace(SCRIPT_TAG, inlined);

  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(outPath, bundled, "utf8");

  const kb = (Buffer.byteLength(bundled, "utf8") / 1024).toFixed(1);
  console.log(`Built ${path.relative(projectRoot, outPath)} (${kb} KB, self-contained).`);
}

build();
