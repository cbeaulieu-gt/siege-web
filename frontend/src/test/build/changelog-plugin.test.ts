/**
 * changelog-plugin unit tests — path resolution
 *
 * Covers the findChangelogPath / changelogCandidatePaths helpers that were
 * introduced to fix the Docker build context failure (#302).
 *
 * findChangelogPath accepts an optional `checker` argument (injected existsSync).
 * Tests pass a stub so no filesystem I/O occurs and search-order logic is explicit.
 */

import { describe, it, expect } from "vitest";
import { resolve } from "path";
import {
  findChangelogPath,
  changelogCandidatePaths,
} from "../../build/changelog-plugin";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Fake dirname representing the dev layout: <repo>/frontend/src/build/ */
const DEV_DIRNAME = "/repo/frontend/src/build";

/** Fake dirname representing the Docker layout: /app/src/build/ */
const DOCKER_DIRNAME = "/app/src/build";

// ---------------------------------------------------------------------------
// Tests: dev path resolves first
// ---------------------------------------------------------------------------

describe("findChangelogPath — dev path", () => {
  it("returns the dev candidate when only the dev path exists", () => {
    const devCandidate = resolve(DEV_DIRNAME, "../../../CHANGELOG.md");
    const result = findChangelogPath(DEV_DIRNAME, (p) => p === devCandidate);
    expect(result).toBe(devCandidate);
  });
});

// ---------------------------------------------------------------------------
// Tests: Docker path resolves as fallback
// ---------------------------------------------------------------------------

describe("findChangelogPath — docker path", () => {
  it("returns the docker candidate when the dev path is absent", () => {
    // Simulate Docker context: /app/src/build — the three-level traversal yields
    // /CHANGELOG.md (absent); two-level gives /app/CHANGELOG.md (present).
    const devCandidate = resolve(DOCKER_DIRNAME, "../../../CHANGELOG.md");
    const dockerCandidate = resolve(DOCKER_DIRNAME, "../../CHANGELOG.md");

    const result = findChangelogPath(
      DOCKER_DIRNAME,
      (p) => p !== devCandidate && p === dockerCandidate
    );
    expect(result).toBe(dockerCandidate);
  });
});

// ---------------------------------------------------------------------------
// Tests: both missing → returns undefined
// ---------------------------------------------------------------------------

describe("findChangelogPath — both paths missing", () => {
  it("returns undefined when neither candidate exists", () => {
    const result = findChangelogPath(DEV_DIRNAME, () => false);
    expect(result).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Tests: error message contains both candidate paths
// ---------------------------------------------------------------------------

describe("changelogCandidatePaths — error message coverage", () => {
  it("returns exactly two candidate paths", () => {
    const paths = changelogCandidatePaths(DEV_DIRNAME);
    expect(paths).toHaveLength(2);
  });

  it("first candidate is the three-level traversal (dev path)", () => {
    const paths = changelogCandidatePaths(DEV_DIRNAME);
    expect(paths[0]).toBe(resolve(DEV_DIRNAME, "../../../CHANGELOG.md"));
  });

  it("second candidate is the two-level traversal (docker path)", () => {
    const paths = changelogCandidatePaths(DEV_DIRNAME);
    expect(paths[1]).toBe(resolve(DEV_DIRNAME, "../../CHANGELOG.md"));
  });

  it("both candidate paths end with CHANGELOG.md", () => {
    const paths = changelogCandidatePaths(DEV_DIRNAME);
    for (const p of paths) {
      expect(p.endsWith("CHANGELOG.md")).toBe(true);
    }
  });
});
