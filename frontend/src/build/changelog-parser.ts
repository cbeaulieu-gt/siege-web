/**
 * changelog-parser.ts
 *
 * Pure function to parse Keep-a-Changelog formatted markdown into a typed
 * array of ChangelogEntry objects.
 *
 * Design decisions:
 *
 * 1. [Unreleased] handling:
 *    - `includeUnreleased: false` (the default) silently drops the block —
 *      prod builds exclude WIP content.
 *    - `includeUnreleased: true` includes it first in the array with
 *      `version: "Unreleased"` and `releaseDate: ""` as a sentinel value
 *      (empty string, not null, to keep the type `string` throughout).
 *    - In dev (`config.command === "serve"`) the Vite plugin passes
 *      `includeUnreleased: true`; prod passes `false`. See changelog-plugin.ts.
 *
 * 2. Section schema — Record<string, string[]>:
 *    The CHANGELOG uses bold sub-headers (e.g. **Siege lifecycle**) as visual
 *    grouping inside `### Added`. These are NOT treated as separate keys.
 *    They are stripped (the bold line is skipped), and the bullets that follow
 *    are captured under the parent section heading as a flat list. This
 *    matches the `Record<string, string[]>` schema from the issue spec without
 *    introducing a nested structure.
 *
 * 3. Loud failure:
 *    The function throws `Error` (never returns an empty array silently) when:
 *    - The input string is empty.
 *    - No version headings are found (e.g. `## [1.0.0] - YYYY-MM-DD`).
 *    - A version heading has a date that does not match YYYY-MM-DD format.
 *
 * No filesystem or Vite imports — pure string-in / array-out.
 */

/** A single changelog entry parsed from one `## [version] - date` block. */
export interface ChangelogEntry {
  /** Semver string (e.g. "1.0.0") or the sentinel "Unreleased". */
  version: string;
  /** ISO 8601 date string (e.g. "2026-04-17"), or "" for Unreleased. */
  releaseDate: string;
  /** Map of section name → flat array of bullet strings. */
  sections: Record<string, string[]>;
}

/** Options controlling parser behaviour. */
export interface ParseChangelogOptions {
  /**
   * When true, include the `[Unreleased]` block as the first entry.
   * Defaults to false.
   */
  includeUnreleased?: boolean;
}

// Matches:  ## [1.0.0] - 2026-04-17
const VERSION_HEADING_RE = /^## \[([^\]]+)\](?: - (\S+))?$/;

// Matches:  YYYY-MM-DD
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

// Matches:  ### Section Name
const SECTION_HEADING_RE = /^### (.+)$/;

// Matches a list item bullet:  - text  or  * text
const BULLET_RE = /^[-*] (.+)$/;

// Matches a bold sub-header used for visual grouping:  **text**
// These carry no unique content — skip the line itself; keep the bullets.
const BOLD_SUBHEADER_RE = /^\*\*[^*]+\*\*$/;

// Matches link reference definitions at the end:  [1.0.0]: https://...
const LINK_REF_RE = /^\[[^\]]+\]:/;

/**
 * Parse a Keep-a-Changelog formatted markdown string into typed entries.
 *
 * Returns entries in latest-first order (Unreleased first when included,
 * then descending by position in the file which by convention is newest-first).
 *
 * @param markdown - Full text of CHANGELOG.md.
 * @param opts - Parser options (see ParseChangelogOptions).
 * @returns Array of ChangelogEntry, latest first.
 * @throws Error if the input is empty, has no version headings, or contains
 *   a version line with a malformed date.
 */
export function parseChangelog(
  markdown: string,
  opts: ParseChangelogOptions = {}
): ChangelogEntry[] {
  const { includeUnreleased = false } = opts;

  if (!markdown.trim()) {
    throw new Error(
      "CHANGELOG is empty. The changelog file must contain at least one " +
        "version heading (e.g. ## [1.0.0] - 2026-01-01)."
    );
  }

  const lines = markdown.split(/\r?\n/);
  const entries: ChangelogEntry[] = [];

  let currentEntry: ChangelogEntry | null = null;
  let currentSection: string | null = null;

  for (const line of lines) {
    // Skip link reference definitions at the bottom of the file.
    if (LINK_REF_RE.test(line)) {
      continue;
    }

    const versionMatch = VERSION_HEADING_RE.exec(line);
    if (versionMatch) {
      // Flush the previous entry before starting a new one.
      if (currentEntry !== null) {
        entries.push(currentEntry);
      }

      const version = versionMatch[1];
      const rawDate = versionMatch[2] ?? "";

      if (version === "Unreleased") {
        currentEntry = { version: "Unreleased", releaseDate: "", sections: {} };
        currentSection = null;
        continue;
      }

      // For real version entries, a date is required and must be YYYY-MM-DD.
      if (!rawDate) {
        throw new Error(
          `Malformed CHANGELOG: version heading "## [${version}]" is missing a ` +
            `release date. Expected format: ## [${version}] - YYYY-MM-DD.`
        );
      }

      if (!ISO_DATE_RE.test(rawDate)) {
        throw new Error(
          `Malformed CHANGELOG: version "${version}" has an invalid date ` +
            `"${rawDate}". Expected ISO 8601 format YYYY-MM-DD ` +
            `(e.g. ## [${version}] - 2026-01-15).`
        );
      }

      currentEntry = { version, releaseDate: rawDate, sections: {} };
      currentSection = null;
      continue;
    }

    if (currentEntry === null) {
      // Lines before the first version heading (e.g. the top-level # title).
      continue;
    }

    const sectionMatch = SECTION_HEADING_RE.exec(line);
    if (sectionMatch) {
      currentSection = sectionMatch[1];
      if (!(currentSection in currentEntry.sections)) {
        currentEntry.sections[currentSection] = [];
      }
      continue;
    }

    // Bold sub-headers used as visual grouping within a section.
    // Skip the line itself — the bullets that follow belong to currentSection.
    if (BOLD_SUBHEADER_RE.test(line.trim())) {
      continue;
    }

    const bulletMatch = BULLET_RE.exec(line);
    if (bulletMatch && currentSection !== null) {
      currentEntry.sections[currentSection].push(bulletMatch[1]);
      continue;
    }
  }

  // Flush the last entry.
  if (currentEntry !== null) {
    entries.push(currentEntry);
  }

  // Guard: if every entry is Unreleased (or none at all), the file lacks
  // real version headings.
  const hasVersionedEntry = entries.some((e) => e.version !== "Unreleased");
  if (!hasVersionedEntry) {
    throw new Error(
      "Malformed CHANGELOG: no version headings found. " +
        "Expected at least one entry in the format ## [1.0.0] - YYYY-MM-DD."
    );
  }

  // Apply includeUnreleased filter and return.
  // Entries are already in file order (newest first by convention).
  if (includeUnreleased) {
    return entries;
  }
  return entries.filter((e) => e.version !== "Unreleased");
}
