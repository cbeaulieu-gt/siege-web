/**
 * changelog-plugin.ts
 *
 * Vite plugin that exposes the parsed CHANGELOG.md as a virtual module so
 * frontend code can do:
 *
 *   import { changelog } from "virtual:changelog";
 *
 * Design decisions:
 *
 * 1. [Unreleased] visibility policy:
 *    - dev (`config.command === "serve"`): Unreleased block IS included.
 *      Developers can preview WIP entries while working locally.
 *    - prod (`config.command === "build"`): Unreleased block is EXCLUDED.
 *      End users only see released changes.
 *
 * 2. Loud failure:
 *    If CHANGELOG.md is missing or malformed, the plugin throws during the
 *    Vite build/serve startup (via the `load` hook). Vite surfaces this as a
 *    build error so the developer is notified immediately rather than
 *    silently receiving an empty changelog.
 *
 * 3. Virtual module pattern:
 *    - Virtual ID: "virtual:changelog"
 *    - Resolved ID: "\0virtual:changelog" (Vite convention: null-byte prefix
 *      prevents the module from being confused with a real file path).
 */

import { readFileSync, existsSync } from "fs";
import { resolve } from "path";
import type { Plugin, ResolvedConfig } from "vite";
import { parseChangelog } from "./changelog-parser";

/**
 * Locate CHANGELOG.md by searching candidate paths in priority order.
 *
 * Dev: `__dirname` = `<repo>/frontend/src/build/` → `../../../` hits the repo root.
 * Docker: build context is `./frontend/` (copied to `/app/`), so the repo root path
 * won't exist; instead CHANGELOG.md is staged into `frontend/` → `../../` from here.
 * The first path that exists wins; if none exist the caller throws a descriptive error.
 *
 * @param dirname - Directory to resolve candidates from (typically `__dirname`).
 * @param checker - Optional override for `existsSync`; used in tests to avoid I/O.
 */
export function findChangelogPath(
  dirname: string,
  checker: (p: string) => boolean = existsSync
): string | undefined {
  const candidatePaths = changelogCandidatePaths(dirname);
  return candidatePaths.find((p) => checker(p));
}

/** All candidate paths tried by findChangelogPath, for error messages. */
export function changelogCandidatePaths(dirname: string): string[] {
  return [
    resolve(dirname, "../../../CHANGELOG.md"),
    resolve(dirname, "../../CHANGELOG.md"),
  ];
}

const VIRTUAL_MODULE_ID = "virtual:changelog";
const RESOLVED_VIRTUAL_MODULE_ID = "\0" + VIRTUAL_MODULE_ID;

/**
 * Vite plugin factory that resolves `virtual:changelog` to a JSON module
 * containing the parsed CHANGELOG.md entries.
 *
 * @returns Vite Plugin object.
 */
export function changelogPlugin(): Plugin {
  let resolvedConfig: ResolvedConfig;

  return {
    name: "vite-plugin-changelog",

    configResolved(config) {
      resolvedConfig = config;
    },

    resolveId(id) {
      if (id === VIRTUAL_MODULE_ID) {
        return RESOLVED_VIRTUAL_MODULE_ID;
      }
      return undefined;
    },

    load(id) {
      if (id !== RESOLVED_VIRTUAL_MODULE_ID) {
        return undefined;
      }

      // Locate CHANGELOG.md — search candidate paths so both dev (repo root via
      // traversal) and Docker (file staged into the frontend build context) work.
      const changelogPath = findChangelogPath(__dirname);

      if (!changelogPath) {
        const tried = changelogCandidatePaths(__dirname);
        throw new Error(
          `[changelog-plugin] CHANGELOG.md not found at any of: ${tried.join(", ")}. ` +
            "Ensure the file exists at the repository root, or — for Docker builds — " +
            "that it has been staged into the frontend build context."
        );
      }

      let markdown: string;
      try {
        markdown = readFileSync(changelogPath, "utf-8");
      } catch (err) {
        throw new Error(
          `[changelog-plugin] Failed to read CHANGELOG.md: ${String(err)}`
        );
      }

      // Include Unreleased entries in dev (serve) mode only.
      const includeUnreleased = resolvedConfig.command === "serve";

      let entries;
      try {
        entries = parseChangelog(markdown, { includeUnreleased });
      } catch (err) {
        throw new Error(
          `[changelog-plugin] CHANGELOG.md is malformed — build aborted. ` +
            `Fix the changelog and retry.\n\nDetails: ${String(err)}`
        );
      }

      // Emit as a plain ES module that exports a named `changelog` binding.
      // JSON.stringify is safe here because ChangelogEntry contains only
      // strings and arrays of strings.
      return `export const changelog = ${JSON.stringify(entries, null, 2)};`;
    },
  };
}

export default changelogPlugin;
