// @ts-check
"use strict";

// Companion of the sentence-per-line rule (MD100): breaks, in place, the lines the
// rule flagged as two sentences on one line. It reads markdownlint-cli2's output on
// its standard input and resolves the file names it finds against the working
// directory, as markdownlint-cli2 printed them:
//
//   markdownlint-cli2 | node split-sentences.js
//
// It touches only the lines the rule flagged, and only at the rule's own sentence
// boundary: line breaks carry no rendered meaning, so the text is unchanged.
// A list item's continuation lines are indented under its text.
// The other shape the rule flags, a sentence broken across lines, needs a human:
// whether to join the lines or to end the sentence is not for a tool to say.
//
// The boundary below is a copy of sentence-per-line.js's. If the two drift, the
// tool leaves violations behind rather than breaking text wrongly, which
// tests/test_split_sentences.py catches.

const fs = require("fs");

const CLOSERS = "\"')\\]”’»*_";
const OPENERS = "A-Z(“\"'«*_`\\[";
const INTERNAL_BOUNDARY = new RegExp("[.!?][" + CLOSERS + "]*\\s+(?=[" + OPENERS + "])");
const ABBR = "e\\.g|i\\.e|cf|vs|etc|al|ibid|no|nos|dr|mr|mrs|ms|st|fig|eq|ch|pp|vol|approx|ph\\.d|u\\.s|a\\.k\\.a";
const OPEN_PREFIX = "(?:^|[\\s(*_])";
const ENDS_ABBR = new RegExp(OPEN_PREFIX + "(?:" + ABBR + ")\\.$", "i");
const ENDS_INITIAL = new RegExp(OPEN_PREFIX + "[A-Z]\\.$");
const ENDS_DECIMAL = /\d\.$/;
const LIST_MARKER = /^\s*(?:[-*+]|\d+\.)\s+/;

/** The lines markdownlint-cli2 flagged as two sentences, per file (1-based). */
function flaggedLines(report) {
  /** @type {Map<string, Set<number>>} */
  const flagged = new Map();
  for (const line of report.split("\n")) {
    const m = /^(\S+?):(\d+)(?::\d+)? (?:(?:error|warning) )?sentence-per-line\/MD100 .*Two sentences/.exec(line);
    if (m) {
      if (!flagged.has(m[1])) {
        flagged.set(m[1], new Set());
      }
      flagged.get(m[1])?.add(Number(m[2]));
    }
  }
  return flagged;
}

/** One line, as the lines it becomes. */
function split(line) {
  const marker = LIST_MARKER.exec(line);
  const indent = marker ? " ".repeat(marker[0].length) : "";
  const lines = [];
  let rest = line;
  let from = 0;
  for (;;) {
    const m = INTERNAL_BOUNDARY.exec(rest.slice(from));
    if (!m) {
      break;
    }
    const at = from + m.index;
    const before = rest.slice(0, at + 1);
    const end = at + m[0].length;
    if (ENDS_ABBR.test(before) || ENDS_INITIAL.test(before) || ENDS_DECIMAL.test(before)) {
      from = end;
      continue;
    }
    lines.push(rest.slice(0, end).replace(/\s+$/, ""));
    rest = indent + rest.slice(end);
    from = indent.length;
  }
  lines.push(rest);
  return lines;
}

for (const [file, numbers] of flaggedLines(fs.readFileSync(0, "utf8"))) {
  const lines = fs.readFileSync(file, "utf8").split("\n");
  const result = lines.flatMap((line, i) => (numbers.has(i + 1) ? split(line) : [line]));
  fs.writeFileSync(file, result.join("\n"));
}
