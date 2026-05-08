/**
 * changelog-parser unit tests
 *
 * Covers:
 *  - Parses the real CHANGELOG.md correctly: v1.0.0 entry present with
 *    expected sections (Added, Security, Infrastructure, Developer Experience)
 *  - Versions returned in latest-first order
 *  - includeUnreleased: false (default) excludes [Unreleased] block
 *  - includeUnreleased: true includes [Unreleased] with sentinel values
 *  - Malformed input throws: empty string
 *  - Malformed input throws: no version heading found
 *  - Malformed input throws: malformed date in version line
 *  - Section bullets flattened to strings under Record<string, string[]>;
 *    bold subsection headers (e.g. **Siege lifecycle**) are stripped and their
 *    following bullets are still captured under the parent section (Added).
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";
import { parseChangelog } from "../../build/changelog-parser";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Path to the real CHANGELOG.md at the repo root (two levels up from frontend/). */
const REAL_CHANGELOG_PATH = resolve(__dirname, "../../../../CHANGELOG.md");

function loadRealChangelog(): string {
  return readFileSync(REAL_CHANGELOG_PATH, "utf-8");
}

// A minimal well-formed changelog used for isolated unit tests.
const MINIMAL_CHANGELOG = `# Changelog

## [Unreleased]

### Added
- Unreleased feature

## [2.0.0] - 2026-06-01

### Added
- New widget

### Fixed
- Bug in widget

## [1.0.0] - 2026-01-15

### Added
- Initial release

[Unreleased]: https://example.com/compare/v2.0.0...HEAD
[2.0.0]: https://example.com/releases/tag/v2.0.0
[1.0.0]: https://example.com/releases/tag/v1.0.0
`;

// ---------------------------------------------------------------------------
// Tests: real CHANGELOG.md
// ---------------------------------------------------------------------------

describe("parseChangelog — real CHANGELOG.md", () => {
  it("returns at least the v1.0.0 entry", () => {
    const entries = parseChangelog(loadRealChangelog());
    const v1 = entries.find((e) => e.version === "1.0.0");
    expect(v1).toBeDefined();
  });

  it("v1.0.0 entry has the expected sections", () => {
    const entries = parseChangelog(loadRealChangelog());
    const v1 = entries.find((e) => e.version === "1.0.0");
    expect(v1).toBeDefined();
    const sectionNames = Object.keys(v1!.sections);
    expect(sectionNames).toContain("Added");
    expect(sectionNames).toContain("Security");
    expect(sectionNames).toContain("Infrastructure");
    expect(sectionNames).toContain("Developer Experience");
  });

  it("v1.0.0 Added section contains bullets (not empty)", () => {
    const entries = parseChangelog(loadRealChangelog());
    const v1 = entries.find((e) => e.version === "1.0.0");
    expect(v1!.sections["Added"].length).toBeGreaterThan(0);
  });

  it("v1.0.0 release date is 2026-04-17", () => {
    const entries = parseChangelog(loadRealChangelog());
    const v1 = entries.find((e) => e.version === "1.0.0");
    expect(v1!.releaseDate).toBe("2026-04-17");
  });

  it("excludes [Unreleased] by default", () => {
    const entries = parseChangelog(loadRealChangelog());
    const unreleased = entries.find((e) => e.version === "Unreleased");
    expect(unreleased).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Tests: ordering
// ---------------------------------------------------------------------------

describe("parseChangelog — ordering", () => {
  it("returns entries in latest-first order", () => {
    const entries = parseChangelog(MINIMAL_CHANGELOG);
    expect(entries[0].version).toBe("2.0.0");
    expect(entries[1].version).toBe("1.0.0");
  });
});

// ---------------------------------------------------------------------------
// Tests: includeUnreleased option
// ---------------------------------------------------------------------------

describe("parseChangelog — includeUnreleased option", () => {
  it("excludes [Unreleased] when includeUnreleased is false (default)", () => {
    const entries = parseChangelog(MINIMAL_CHANGELOG);
    expect(entries.find((e) => e.version === "Unreleased")).toBeUndefined();
  });

  it("excludes [Unreleased] when includeUnreleased is explicitly false", () => {
    const entries = parseChangelog(MINIMAL_CHANGELOG, {
      includeUnreleased: false,
    });
    expect(entries.find((e) => e.version === "Unreleased")).toBeUndefined();
  });

  it("includes [Unreleased] when includeUnreleased is true", () => {
    const entries = parseChangelog(MINIMAL_CHANGELOG, {
      includeUnreleased: true,
    });
    const unreleased = entries.find((e) => e.version === "Unreleased");
    expect(unreleased).toBeDefined();
  });

  it("[Unreleased] entry has empty string as releaseDate sentinel", () => {
    const entries = parseChangelog(MINIMAL_CHANGELOG, {
      includeUnreleased: true,
    });
    const unreleased = entries.find((e) => e.version === "Unreleased");
    expect(unreleased!.releaseDate).toBe("");
  });

  it("[Unreleased] entry is first when included", () => {
    const entries = parseChangelog(MINIMAL_CHANGELOG, {
      includeUnreleased: true,
    });
    expect(entries[0].version).toBe("Unreleased");
  });

  it("[Unreleased] entry captures its sections", () => {
    const entries = parseChangelog(MINIMAL_CHANGELOG, {
      includeUnreleased: true,
    });
    const unreleased = entries.find((e) => e.version === "Unreleased");
    expect(unreleased!.sections["Added"]).toContain("Unreleased feature");
  });
});

// ---------------------------------------------------------------------------
// Tests: sections schema — Record<string, string[]>
// ---------------------------------------------------------------------------

describe("parseChangelog — sections schema", () => {
  it("section values are arrays of strings", () => {
    const entries = parseChangelog(MINIMAL_CHANGELOG);
    for (const entry of entries) {
      for (const [, bullets] of Object.entries(entry.sections)) {
        expect(Array.isArray(bullets)).toBe(true);
        for (const bullet of bullets) {
          expect(typeof bullet).toBe("string");
        }
      }
    }
  });

  it("multiple sections are captured independently", () => {
    const entries = parseChangelog(MINIMAL_CHANGELOG);
    const v2 = entries.find((e) => e.version === "2.0.0");
    expect(v2!.sections["Added"]).toContain("New widget");
    expect(v2!.sections["Fixed"]).toContain("Bug in widget");
  });

  it("bold subsection headers (**text**) are stripped from bullet text", () => {
    // The real CHANGELOG uses bold sub-headers like **Siege lifecycle** as
    // visual grouping inside a section; they are not actual bullets.
    // The parser should skip these lines (they carry no bullet content).
    const entries = parseChangelog(loadRealChangelog());
    const v1 = entries.find((e) => e.version === "1.0.0");
    const addedBullets = v1!.sections["Added"];
    // None of the bullets should be just a bare bold header
    const hasBoldHeaderOnly = addedBullets.some((b) => /^\*\*[^*]+\*\*$/.test(b));
    expect(hasBoldHeaderOnly).toBe(false);
  });

  it("bullets following bold subsection headers are still captured", () => {
    const entries = parseChangelog(loadRealChangelog());
    const v1 = entries.find((e) => e.version === "1.0.0");
    const addedBullets = v1!.sections["Added"];
    // A known bullet from under **Siege lifecycle** subsection
    const hasKnownBullet = addedBullets.some((b) =>
      b.includes("Full siege lifecycle")
    );
    expect(hasKnownBullet).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Tests: malformed input — loud failures
// ---------------------------------------------------------------------------

describe("parseChangelog — malformed input throws", () => {
  it("throws on empty string", () => {
    expect(() => parseChangelog("")).toThrow();
  });

  it("throws with a message mentioning 'CHANGELOG' or 'version' on empty string", () => {
    expect(() => parseChangelog("")).toThrowError(/changelog|version/i);
  });

  it("throws when no version headings are found", () => {
    const noVersions = "# Changelog\n\nSome text but no version headings.\n";
    expect(() => parseChangelog(noVersions)).toThrow();
  });

  it("throws with a message mentioning 'version' when no version headings found", () => {
    const noVersions = "# Changelog\n\nSome text but no version headings.\n";
    expect(() => parseChangelog(noVersions)).toThrowError(/version/i);
  });

  it("throws when a version line has a malformed date (bad format)", () => {
    const badDate = `# Changelog\n\n## [1.0.0] - 17/04/2026\n\n### Added\n- item\n`;
    expect(() => parseChangelog(badDate)).toThrow();
  });

  it("throws with a message mentioning 'date' when date is malformed", () => {
    const badDate = `# Changelog\n\n## [1.0.0] - 17/04/2026\n\n### Added\n- item\n`;
    expect(() => parseChangelog(badDate)).toThrowError(/date/i);
  });
});
