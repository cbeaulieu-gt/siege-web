/**
 * Ambient module declaration for the virtual:changelog Vite plugin.
 *
 * Allows TypeScript to type-check `import { changelog } from "virtual:changelog"`
 * without a real file on disk.
 *
 * The ChangelogEntry shape mirrors the type exported from
 * src/build/changelog-parser.ts.
 */

declare module "virtual:changelog" {
  /** A single changelog entry parsed from one `## [version] - date` block. */
  export interface ChangelogEntry {
    /** Semver string (e.g. "1.0.0") or the sentinel "Unreleased". */
    version: string;
    /**
     * ISO 8601 date string (e.g. "2026-04-17").
     * Empty string "" for the [Unreleased] entry.
     */
    releaseDate: string;
    /**
     * Map of section name → flat array of bullet strings.
     * Section names come from `### Heading` lines in the changelog
     * (e.g. "Added", "Fixed", "Security").
     */
    sections: Record<string, string[]>;
  }

  /**
   * Parsed changelog entries, latest-first.
   *
   * In production builds the [Unreleased] block is excluded.
   * In development (Vite serve mode) the [Unreleased] block is first
   * (version: "Unreleased", releaseDate: "").
   */
  export const changelog: ChangelogEntry[];
}
