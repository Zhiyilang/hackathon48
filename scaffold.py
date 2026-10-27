"""Scaffold a zero-dependency Python project ready for a 48-hour hackathon.

Why this exists
---------------
A hackathon project fails for two reasons, and neither is "the idea was bad":

1. The last 90 minutes are spent fighting environment and encoding bugs
   instead of finishing the demo.
2. The judges cannot tell what is real, because there is no reproducible
   evidence - only prose claims.

This generator produces a skeleton that pre-empts both. Every skeleton is
born green: ``python eval.py`` passes immediately, so every subsequent
assertion you add is a real regression test rather than a rescue operation.

Five defences are baked in, each one copied from a defect that actually
occurred in a shipped project (see ``DEFENCES`` for the incident behind
each). They are shipped as *seed assertions*, not comments - a defence
nobody executes is a defence nobody has.

Usage
-----
    python scaffold.py NAME                 # create ./NAME from scratch
    python scaffold.py NAME --dir OUT       # create ./OUT/NAME
    python scaffold.py --selfcheck          # generate, verify, report

Zero dependency: standard library only.
"""

import argparse
import io
import os
import shutil
import subprocess
import sys
import tempfile

DEFENCES = (
    ("money", "Amounts are integers in minor units with half-up rounding. "
              "Banker's rounding once turned 0.005 into 0 silently."),
    ("units", "Values carrying different units never compare equal unless a "
              "conversion is supplied explicitly."),
    ("alias", "Column aliases resolve independently; a payment reference is "
              "never silently overwritten by a row id."),
    ("stdout", "Output survives LC_ALL=C. A non-UTF-8 console once crashed "
               "the CLI with UnicodeEncodeError mid-demo."),
    ("evidence", "Every verdict carries the evidence behind it, and says "
                 "UNKNOWN rather than guessing when evidence is missing."),
)

CORE = '''"""Core building blocks for __PKG__.

Kept deliberately boring: these four helpers are where hackathon projects
usually lose their last hour.
"""

from __future__ import annotations

import decimal
import io
import os
import sys

MISSING = object()


# --- defence: money ---------------------------------------------------------
def parse_money(text):
    """Parse money into integer minor units (cents), half-up.

    Never ``float`` and never Python's ``round()``: banker's rounding maps
    0.005 to 0, which silently deletes half a cent - exactly the class of
    accident a reconciliation tool exists to catch.
    """
    if text is None:
        return None
    s = str(text).strip().replace(",", "").replace(" ", "")
    if not s:
        return None
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]
    if s.startswith("+"):
        s = s[1:]
    if s.startswith("-"):
        negative = True
        s = s[1:]
    if not s:
        return None
    minor_units = 2
    rate = decimal.Decimal(10) ** minor_units
    try:
        value = decimal.Decimal(s)
    except decimal.InvalidOperation:
        return None
    scaled = (value * rate).quantize(decimal.Decimal(1),
                                     rounding=decimal.ROUND_HALF_UP)
    minor = int(scaled)
    return -minor if negative else minor


def money_equal(a, b, tolerance=0):
    """Compare two integer minor-unit amounts."""
    if a is None or b is None:
        return False
    return abs(a - b) <= tolerance


# --- defence: units ---------------------------------------------------------
class Quantity(object):
    """A value that refuses to be compared across units."""

    __slots__ = ("amount", "unit")

    def __init__(self, amount, unit):
        self.amount = amount
        self.unit = str(unit).strip().upper()

    def converted(self, unit, rates):
        unit = str(unit).strip().upper()
        if unit == self.unit:
            return self
        key = (self.unit, unit)
        if key not in rates:
            return None           # honest failure, never a silent 1.0
        return Quantity(int(round(self.amount * rates[key])), unit)

    def __repr__(self):
        return "Quantity(%r, %r)" % (self.amount, self.unit)


def comparable(a, b, rates=None):
    """True only when both carry the same unit, or a rate is supplied."""
    if a.unit == b.unit:
        return True
    if not rates:
        return False
    return a.converted(b.unit, rates) is not None


# --- defence: alias ---------------------------------------------------------
def pick(row, aliases, default=MISSING):
    """Resolve a field through independent alias lists.

    Each alias list is tried in full before the next one, so an identity
    column can never shadow a payment reference.
    """
    for group in aliases:
        for key in group:
            for actual in row:
                if str(actual).strip().lower() == key.lower():
                    value = row[actual]
                    if value is not None and str(value).strip() != "":
                        return str(value).strip()
    if default is MISSING:
        return None
    return default


ALIAS_ID = (("id", "row_id", "编号"),)
ALIAS_REF = (("ref", "reference", "payment_ref", "凭证号"),)
ALIAS_DESC = (("description", "desc", "narrative", "摘要", "memo"),)


# --- defence: evidence ------------------------------------------------------
class Finding(object):
    """A verdict that can be audited, not just believed."""

    __slots__ = ("subject", "verdict", "evidence", "confidence")

    def __init__(self, subject, verdict, evidence=(), confidence=0.0):
        self.subject = subject
        self.verdict = verdict
        self.evidence = tuple(evidence)
        self.confidence = confidence

    def explain(self):
        lines = ["%s -> %s (confidence %.2f)"
                 % (self.subject, self.verdict, self.confidence)]
        for item in self.evidence:
            lines.append("  because: %s" % item)
        if not self.evidence:
            lines.append("  no evidence recorded")
        return "\\n".join(lines)

    def __repr__(self):
        return "Finding(%r, %r, %d evidence)" % (self.subject, self.verdict,
                                                 len(self.evidence))


UNKNOWN = "UNKNOWN"


def explain_all(findings):
    return "\\n".join(f.explain() for f in findings)


# --- defence: stdout --------------------------------------------------------
def write_out(text, stream=None):
    """Write text without ever raising UnicodeEncodeError.

    Falls back to writing raw bytes with ``errors="replace"`` when the
    console encoding cannot represent the text, so a demo cannot die on
    ``LC_ALL=C`` mid-presentation. Deliberately avoids wrapping the stream
    in a TextIOWrapper: that wrapper closes the underlying buffer when it
    is garbage collected.
    """
    stream = stream if stream is not None else sys.stdout
    try:
        stream.write(text)
        return
    except UnicodeEncodeError:
        pass
    encoding = getattr(stream, "encoding", None) or "utf-8"
    encoded = text.encode(encoding, "replace")
    buf = getattr(stream, "buffer", None)
    if buf is not None:
        buf.write(encoded)
        buf.flush()
        return
    stream.write(encoded.decode(encoding, "replace"))


def read_text(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)
    return path
'''

INIT = '''"""__NAME__ - <one line describing what it does>.

Zero dependency: standard library only. Run ``python eval.py`` to verify.
"""

from .core import (Finding, Quantity, UNKNOWN, comparable, explain_all,
                   money_equal, parse_money, pick)

__all__ = ["Finding", "Quantity", "UNKNOWN", "comparable", "explain_all",
           "money_equal", "parse_money", "pick"]
__version__ = "0.1.0"
'''

MAIN = '''"""Command line entry point: ``python -m __PKG__``."""

from __future__ import annotations

import argparse
import io
import os
import sys

from .core import write_out


def build_parser():
    p = argparse.ArgumentParser(prog="__PKG__",
                                description="__NAME__")
    p.add_argument("paths", nargs="*", help="input files")
    p.add_argument("--json", dest="json_path", default=None,
                   help="write JSON report to this path")
    p.add_argument("--version", action="version",
                   version="%(prog)s " + __import__("__PKG__").__version__)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    from .core import Finding, explain_all

    # Replace this with your real pipeline.
    findings = [Finding(subject=("<stdin>" if not args.paths else
                                 ", ".join(args.paths)),
                        verdict="__PKG__ skeleton is running",
                        evidence=("scaffold-generated project",),
                        confidence=1.0)]
    write_out(explain_all(findings) + "\\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

EVAL = '''# -*- coding: utf-8 -*-
"""Offline assertion suite for __NAME__.

Run:  python eval.py
Exit code 0 means every assertion passed.

The suite is the specification: if a behaviour matters, it is asserted here.
Seed assertions below cover the five defences this skeleton ships with; add
one assertion per claim you make anywhere else in the project.
"""

from __future__ import annotations

import decimal
import io
import os
import runpy
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import __PKG__ as pkg

PASSED = []
FAILED = []


def eq(name, got, want):
    if got == want:
        PASSED.append(name)
    else:
        FAILED.append("%s: got %r, want %r" % (name, got, want))


def ok(name, cond, detail=""):
    if cond:
        PASSED.append(name)
    else:
        FAILED.append("%s: %s" % (name, detail or "condition false"))


# --- defence 1: money -------------------------------------------------------
from __PKG__.core import parse_money, money_equal

eq("money.half_up_at_half_cent", parse_money("0.005"), 1)
eq("money.half_up_at_1.005", parse_money("1.005"), 101)
eq("money.half_up_at_2.675", parse_money("2.675"), 268)
eq("money.thousands_separator", parse_money("1,234.56"), 123456)
eq("money.parenthesised_negative", parse_money("(12.34)"), -1234)
eq("money.explicit_negative", parse_money("-12.34"), -1234)
eq("money.empty_is_none", parse_money(""), None)
eq("money.garbage_is_none", parse_money("abc"), None)
ok("money.never_float", not isinstance(parse_money("1.00"), float),
   "minor units must stay integral")
eq("money.tolerance_respected", money_equal(100, 101, tolerance=1), True)
eq("money.tolerance_enforced", money_equal(100, 102, tolerance=1), False)

# --- defence 2: units -------------------------------------------------------
from __PKG__.core import Quantity, comparable

q_cny = Quantity(10000, "CNY")
q_usd = Quantity(10000, "USD")
ok("units.same_unit_comparable", comparable(q_cny, Quantity(10000, "CNY")))
ok("units.cross_unit_rejected", not comparable(q_cny, q_usd),
   "different units must not compare without a rate")
ok("units.converted_is_none_without_rate", q_cny.converted("USD", {}) is None,
   "missing rate must fail loudly, never default to 1.0")
conv = q_cny.converted("USD", {("CNY", "USD"): 0.14})
ok("units.converted_applies_rate", conv is not None and conv.amount == 1400,
   "rate applied")
ok("units.cross_unit_ok_with_rate", comparable(q_cny, q_usd,
                                               {("CNY", "USD"): 0.14}))

# --- defence 3: alias resolution -------------------------------------------
from __PKG__.core import pick, ALIAS_ID, ALIAS_REF, ALIAS_DESC

row = {"id": "row-7", "ref": "INV-1", "description": "invoice"}
eq("alias.ref_not_shadowed_by_id", pick(row, ALIAS_REF), "INV-1")
eq("alias.id_resolves", pick(row, ALIAS_ID), "row-7")
eq("alias.desc_resolves", pick(row, ALIAS_DESC), "invoice")
row_missing_ref = {"id": "row-8", "description": "no ref"}
eq("alias.missing_ref_is_none", pick(row_missing_ref, ALIAS_REF), None)
ok("alias.ref_distinct_from_id",
   pick(row, ALIAS_REF) != pick(row, ALIAS_ID),
   "reference and identity must never collapse onto the same column")
eq("alias.case_insensitive",
   pick({"REF": "X-1"}, ALIAS_REF), "X-1")
eq("alias.blank_falls_back_to_default",
   pick({"ref": "   "}, ALIAS_REF, default="NONE"), "NONE")

# --- defence 4: stdout under a hostile locale ------------------------------
from __PKG__.core import write_out


class _AsciiSink(object):
    """A stream that rejects non-ASCII, mimicking LC_ALL=C."""

    encoding = "ascii"

    def __init__(self):
        self.buffer = io.BytesIO()

    def write(self, text):
        text.encode("ascii")          # raises UnicodeEncodeError on non-ASCII
        self.buffer.write(text.encode("ascii"))
        return len(text)


sink = _AsciiSink()
try:
    write_out(u"发票 \\u4e2d\\u6587 amount 100.00\\n", stream=sink)
    ok("stdout.survives_ascii_console", True)
except UnicodeEncodeError as exc:
    ok("stdout.survives_ascii_console", False, str(exc))
ok("stdout.emitted_something", sink.buffer.getvalue().decode("ascii") != "",
   "nothing written")

# --- defence 5: evidence chain ---------------------------------------------
from __PKG__.core import Finding, UNKNOWN, explain_all

f_evidenced = Finding("pair#1", "MATCHED",
                      ("same amount", "same day", "same reference"), 0.9)
f_unknown = Finding("pair#2", UNKNOWN, (), 0.0)
ok("evidence.unknown_has_no_evidence", f_unknown.evidence == (),
   "UNKNOWN must not carry fabricated evidence")
ok("evidence.unknown_has_zero_confidence", f_unknown.confidence == 0.0)
ok("evidence.evidenced_has_support", len(f_evidenced.evidence) == 3)
ok("evidence.explain_includes_reason",
   "same reference" in f_evidenced.explain())
ok("evidence.unknown_explain_is_honest",
   "no evidence recorded" in f_unknown.explain())
ok("evidence.batch_explain_joins",
   explain_all([f_evidenced, f_unknown]).count("->") == 2)

# --- packaging --------------------------------------------------------------
ok("pkg.exports_core_api", hasattr(pkg, "Finding") and hasattr(pkg, "parse_money"))
ok("pkg.has_version", isinstance(getattr(pkg, "__version__", None), str))

HERE = os.path.dirname(os.path.abspath(__file__))
for required in ("README.md", "LICENSE", ".gitignore"):
    ok("repo.has_%s" % required.replace(".", "_"),
       os.path.exists(os.path.join(HERE, required)),
       "missing %s" % required)

# every Python file must be importable and ASCII-clean enough to survive any
# locale: compilation must not depend on the console encoding.
import glob as _glob
for path in sorted(_glob.glob(os.path.join(HERE, "__PKG__", "*.py"))):
    base = os.path.basename(path)
    ok("compile.%s" % base, compile(io.open(path, encoding="utf-8").read(),
                                    path, "exec") is not None)

# --- report -----------------------------------------------------------------
sys.stderr.write("%d passed, %d failed\\n" % (len(PASSED), len(FAILED)))
for line in FAILED:
    sys.stderr.write("  FAIL %s\\n" % line)
sys.exit(1 if FAILED else 0)
'''

CI = '''name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.9", "3.11", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Run offline assertion suite
        run: python eval.py

  hostile-locale:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Run without UTF-8 mode (LC_ALL=C, no PYTHONUTF8)
        env:
          LC_ALL: C
          LANG: C
        run: |
          unset PYTHONUTF8
          python eval.py
'''

README = '''# __NAME__

<One paragraph: what this does, and who suffers without it.>

Zero dependency (standard library only), offline-verifiable.

## Quick start

```bash
python eval.py              # offline assertion suite
python -m __PKG__ --help     # CLI
```

## Layout

```
__PKG__/__init__.py   public surface
__PKG__/core.py       four defensive primitives + evidence type
__PKG__/__main__.py   CLI
eval.py               offline assertion suite (this is the specification)
```

## The five defences baked into this skeleton

| Defence | The incident it came from |
|---|---|
| `money` | Banker's rounding turned `0.005` into `0` - a half cent vanished silently. Amounts live in integer minor units with `ROUND_HALF_UP`. |
| `units` | `100 CNY` was once treated as equal to `100 USD`. Cross-unit comparison now fails unless a conversion rate is supplied. |
| `alias` | A payment reference column was silently overwritten by a row id, quietly demoting the best match class with no error. Alias groups resolve independently. |
| `stdout` | The CLI crashed with `UnicodeEncodeError` on a non-UTF-8 console, mid-demo. All output goes through `write_out`. |
| `evidence` | Verdicts without reasons cannot be audited. Every `Finding` carries its evidence and says `UNKNOWN` rather than guessing. |

Each defence ships as **executable seed assertions** in `eval.py`, not as
comments. Run `python eval.py` to confirm.

## House rules

1. Every claim anywhere in this repo has one assertion in `eval.py`.
2. No new dependency without a reason written down next to it.
3. The suite is green before every commit, including under `LC_ALL=C`.

## License

MIT. See `LICENSE`.
'''

README_ZH = '''# __NAME__

<一段话：它做什么，没有它谁会难受。>

零第三方依赖（仅标准库），可离线验证。

## 快速开始

```bash
python eval.py              # 离线断言套件
python -m __PKG__ --help     # 命令行
```

## 目录

```
__PKG__/__init__.py   对外接口
__PKG__/core.py       四个防御原语 + 证据类型
__PKG__/__main__.py   命令行
eval.py               离线断言套件（这就是规格）
```

## 骨架内置的五道防御

| 防御 | 它来自哪次真实事故 |
|---|---|
| `money` | 银行家舍入把 `0.005` 变成 `0`，半分钱静默消失。金额统一用最小货币单位的整数 + `ROUND_HALF_UP`。 |
| `units` | `100 CNY` 曾被当作等于 `100 USD`。跨单位现在必须给汇率才能比较，缺汇率就失败，绝不默认 1.0。 |
| `alias` | 付款参考列被行 id 静默覆盖，最高质量匹配被无声降级且无任何报错。别名组彼此独立解析。 |
| `stdout` | 演示途中 CLI 在非 UTF-8 控制台下崩 UnicodeEncodeError。所有输出走 `write_out`。 |
| `evidence` | 没有理由的结论无法审计。每条 `Finding` 自带证据，缺证据时说 `UNKNOWN` 而不是猜。 |

每道防御都以**可执行的种子断言**形式落在 `eval.py` 里，而不是注释。跑
`python eval.py` 即可确认。

## 本项目铁律

1. 仓库里任何一处宣称，在 `eval.py` 里有且只有一条断言对应。
2. 新增依赖必须就地写下理由。
3. 每次提交前套件全绿，含 `LC_ALL=C` 敌意 locale。

## 许可

MIT，见 `LICENSE`。
'''

LICENSE = '''MIT License

Copyright (c) 2026 __AUTHOR__

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

GITIGNORE = '''__pycache__/
*.py[cod]
*.egg-info/
build/
dist/
.venv/
venv/
.env
.idea/
.vscode/
.DS_Store
*.log
'''

_FILES = {
    "core": "__PKG__/core.py",
    "init": "__PKG__/__init__.py",
    "main": "__PKG__/__main__.py",
    "eval": "eval.py",
    "readme": "README.md",
    "readme_zh": "README.zh.md",
    "license": "LICENSE",
    "gitignore": ".gitignore",
    "ci": ".github/workflows/ci.yml",
}


def render(template, name, pkg, author):
    return (template.replace("__NAME__", name)
                    .replace("__PKG__", pkg)
                    .replace("__AUTHOR__", author)
                    .replace("__YEAR__", "2026"))


def create(name, out_dir, author="the author", pkg=None, force=False):
    """Create a project skeleton. Returns the created root path."""
    pkg = pkg or name.lower().replace("-", "_").replace(" ", "_")
    root = os.path.join(out_dir, name)
    if os.path.exists(root):
        if not force:
            raise SystemExit("refusing to touch existing path: %s "
                             "(use --force to overwrite)" % root)
        shutil.rmtree(root)

    wrote = []
    for key, rel in _FILES.items():
        target = os.path.join(root, rel.replace("__PKG__", pkg))
        parent = os.path.dirname(target)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        body = render(globals()[key.upper()], name, pkg, author)
        with io.open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        wrote.append(os.path.relpath(target, root))
    return root, wrote


def verify(root, python=sys.executable):
    """Run the generated suite; returns (returncode, output tail)."""
    proc = subprocess.run([python, "eval.py"], cwd=root,
                          capture_output=True, text=True)
    tail = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, tail.strip()


def selfcheck(python=sys.executable):
    """Generate into a temp dir, verify green, also verify hostile locale."""
    tmp = tempfile.mkdtemp(prefix="hack48check_")
    try:
        root, wrote = create("SmokeProj", tmp, author="selfcheck")
        rc, out = verify(root, python)
        print("[scaffold] generated %d files" % len(wrote))
        print("[scaffold] eval.py rc=%d :: %s" % (rc, out.splitlines()[-1]
                                                  if out else ""))

        env = dict(os.environ)
        for key in ("PYTHONUTF8", "PYTHONIOENCODING"):
            env.pop(key, None)
        env["LC_ALL"] = "C"
        env["LANG"] = "C"
        proc = subprocess.run([python, "eval.py"], cwd=root,
                              capture_output=True, text=True, env=env)
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip()
        print("[scaffold] hostile-locale rc=%d :: %s"
              % (proc.returncode, tail.splitlines()[-1] if tail else ""))

        # idempotence: regenerating over itself must work with --force
        create("SmokeProj", tmp, author="selfcheck", force=True)
        rc2, out2 = verify(root, python)
        print("[scaffold] regenerate rc=%d :: %s"
              % (rc2, out2.splitlines()[-1] if out2 else ""))

        green = (rc == 0 and proc.returncode == 0 and rc2 == 0)
        print("[scaffold] SELFCHECK %s" % ("PASS" if green else "FAIL"))
        return 0 if green else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("name", nargs="?", default=None, help="project name")
    p.add_argument("--dir", default=".", help="parent directory")
    p.add_argument("--author", default="the author", help="copyright holder")
    p.add_argument("--pkg", default=None, help="package name override")
    p.add_argument("--force", action="store_true",
                   help="overwrite an existing directory")
    p.add_argument("--selfcheck", action="store_true",
                   help="generate, verify, and exit")
    args = p.parse_args(argv)

    if args.selfcheck:
        return selfcheck()
    if not args.name:
        p.error("a project name is required (or use --selfcheck)")

    parent = args.dir
    if not os.path.isdir(parent):
        os.makedirs(parent)
    root, wrote = create(args.name, parent, author=args.author,
                         pkg=args.pkg, force=args.force)
    print("created %s" % root)
    for rel in sorted(wrote):
        print("  %s" % rel)
    rc, out = verify(root)
    print("eval.py rc=%d" % rc)
    print(out.splitlines()[-1] if out else "")
    return rc


if __name__ == "__main__":
    sys.exit(main())
