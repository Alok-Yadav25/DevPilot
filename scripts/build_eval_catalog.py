"""Materialize the same 25 synthetic cases for the worker and website."""

import json
from pathlib import Path

cases = [
    (
        "Normalize word separators",
        "String handling",
        "Use hyphens between normalized words, never underscores.",
        '"_".join(value.strip().lower().split())',
        '"-".join(value.strip().lower().split())',
        [("Hello World", "hello-world"), (" a   b ", "a-b"), ("", "")],
    ),
    (
        "Normalize identifier case",
        "String handling",
        "Return lowercase identifiers, not uppercase.",
        "value.upper()",
        "value.lower()",
        [("DevPilot", "devpilot"), ("ABC", "abc"), ("", "")],
    ),
    (
        "Trim both ends",
        "String handling",
        "Remove whitespace from both ends of the string.",
        "value.lstrip()",
        "value.strip()",
        [(" a ", "a"), ("right  ", "right"), ("", "")],
    ),
    (
        "Replace every separator",
        "String handling",
        "Replace every underscore with a hyphen, not just the first one.",
        'value.replace("_", "-", 1)',
        'value.replace("_", "-")',
        [("a_b_c", "a-b-c"), ("a", "a"), ("_x_", "-x-")],
    ),
    (
        "Keep an exact prefix",
        "String handling",
        "Remove the prefix pre_ only at the start, preserving the rest.",
        'value.replace("pre_", "")',
        'value.removeprefix("pre_")',
        [("pre_name", "name"), ("xpre_name", "xpre_name"), ("pre_pre_x", "pre_x")],
    ),
    (
        "Respect clamp boundaries",
        "Boundary conditions",
        "Clamp the number to [0, 10], retaining values inside the range.",
        "min(0, max(10, value))",
        "max(0, min(10, value))",
        [(-1, 0), (5, 5), (11, 10), (0, 0), (10, 10)],
    ),
    (
        "Include zero in nonnegative",
        "Boundary conditions",
        "A nonnegative check should accept zero.",
        "value > 0",
        "value >= 0",
        [(-1, False), (0, True), (1, True)],
    ),
    (
        "Include the threshold",
        "Boundary conditions",
        "Values of 18 or above satisfy the threshold.",
        "value > 18",
        "value >= 18",
        [(17, False), (18, True), (19, True)],
    ),
    (
        "Bound the last index",
        "Boundary conditions",
        "Return the final valid index for a list, or -1 when empty.",
        "len(value)",
        "len(value) - 1",
        [([], -1), ([1], 0), ([1, 2, 3], 2)],
    ),
    (
        "Take a complete page",
        "Boundary conditions",
        "Return the first three items, including the third.",
        "value[:2]",
        "value[:3]",
        [([], []), ([1, 2], [1, 2]), ([1, 2, 3, 4], [1, 2, 3])],
    ),
    (
        "Start backoff at one",
        "Off-by-one",
        "Attempt zero must have delay 1; cap exponential delays at 32.",
        "min(32, 2 ** (value + 1))",
        "min(32, 2 ** value)",
        [(0, 1), (1, 2), (9, 32)],
    ),
    (
        "Find a zero-based index",
        "Off-by-one",
        "Return the zero-based index of x in a list.",
        'value.index("x") + 1',
        'value.index("x")',
        [(["x"], 0), (["a", "x"], 1), (["a", "b", "x"], 2)],
    ),
    (
        "Include the range endpoint",
        "Off-by-one",
        "Return integers from zero through the input, inclusively.",
        "list(range(value))",
        "list(range(value + 1))",
        [(0, [0]), (2, [0, 1, 2]), (4, [0, 1, 2, 3, 4])],
    ),
    (
        "Count inclusive intervals",
        "Off-by-one",
        "Count integers in the inclusive interval represented by the pair.",
        "value[1] - value[0]",
        "value[1] - value[0] + 1",
        [([1, 1], 1), ([2, 5], 4), ([-2, 2], 5)],
    ),
    (
        "Read a one-based position",
        "Off-by-one",
        "Read the first item in a nonempty list, which is zero-indexed.",
        "value[1]",
        "value[0]",
        [([4], 4), ([1, 2], 1), (["a", "b"], "a")],
    ),
    (
        "Deduplicate in input order",
        "Collections",
        "Remove duplicates while preserving first-seen order.",
        "sorted(set(value))",
        "list(dict.fromkeys(value))",
        [([3, 1, 3, 2], [3, 1, 2]), ([], []), ([2, 2], [2])],
    ),
    (
        "Flatten nested rows",
        "Collections",
        "Flatten one level of nested lists into a single list.",
        "[row for row in value]",
        "[item for row in value for item in row]",
        [([[1, 2], [3]], [1, 2, 3]), ([], []), ([[], [4]], [4])],
    ),
    (
        "Keep the exact match",
        "Collections",
        "Select values at least 3, including exact matches.",
        "[x for x in value if x > 3]",
        "[x for x in value if x >= 3]",
        [([2, 3, 4], [3, 4]), ([], []), ([3, 3], [3, 3])],
    ),
    (
        "Preserve valid zero values",
        "Collections",
        "Drop None values but retain zero, false, and empty strings.",
        "[x for x in value if x]",
        "[x for x in value if x is not None]",
        [([None, 0, 1], [0, 1]), ([False, "", None], [False, ""]), ([], [])],
    ),
    (
        "Map keys to their values",
        "Collections",
        "Build a dictionary from [keys, values], preserving key/value direction.",
        "dict(zip(value[1], value[0]))",
        "dict(zip(value[0], value[1]))",
        [([["a", "b"], [1, 2]], {"a": 1, "b": 2}), ([[], []], {}), ([["x"], [0]], {"x": 0})],
    ),
    (
        "Convert fractions to percent",
        "Numeric logic",
        "Convert a fraction into its numeric percent representation.",
        "value / 100",
        "value * 100",
        [(0, 0), (0.25, 25), (1, 100)],
    ),
    (
        "Calculate the true mean",
        "Numeric logic",
        "Return the arithmetic mean of a nonempty list.",
        "sum(value) / (len(value) + 1)",
        "sum(value) / len(value)",
        [([2], 2), ([2, 4], 3), ([-3, 3], 0)],
    ),
    (
        "Floor negative numbers",
        "Numeric logic",
        "Round toward negative infinity, including negative inputs.",
        "int(value)",
        '__import__("math").floor(value)',
        [(1.8, 1), (-1.2, -2), (0, 0)],
    ),
    (
        "Return absolute distance",
        "Numeric logic",
        "Return the absolute difference between the two numbers.",
        "value[0] - value[1]",
        "abs(value[0] - value[1])",
        [([1, 5], 4), ([5, 1], 4), ([-2, -2], 0)],
    ),
    (
        "Return the discounted price",
        "Numeric logic",
        "Return the final price after a 20 percent discount, not the savings.",
        "value * 0.2",
        "value * 0.8",
        [(100, 80), (0, 0), (50, 40)],
    ),
]
output = []
for i, (name, category, issue, bug, fix, tests) in enumerate(cases, 1):
    output.append(
        dict(
            id=f"case-{i:02}",
            name=name,
            category=category,
            bug_description=issue,
            bug=bug,
            fix=fix,
            tests=tests,
        )
    )
Path("backend/app/evaluation_cases.json").write_text(json.dumps(output, indent=2) + "\n")
Path("frontend/src/lib/evaluation-cases.json").write_text(
    json.dumps(
        [{k: v for k, v in c.items() if k in {"id", "name", "category"}} for c in output], indent=2
    )
    + "\n"
)
