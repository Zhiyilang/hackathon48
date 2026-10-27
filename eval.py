# -*- coding: utf-8 -*-
"""Assertion suite for hackathon48 itself.

The package preaches 'every claim has one assertion'. This file is that
sermon applied to the preachers: everything README.md promises about
scaffold.py is checked here, including that a generated project is born
green under a hostile locale.

Run:  python eval.py
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

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


def _run(args, cwd=None, env=None):
    """Run python with UTF-8 forced for the CHILD, but keep OUR OWN stdout
    ASCII-safe so this suite can run under LC_ALL=C too."""
    child_env = dict(os.environ)
    child_env["PYTHONUTF8"] = "1"
    if env:
        child_env.update(env)
    return subprocess.run([sys.executable] + args, cwd=cwd or HERE,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          env=child_env)


def _tail(proc):
    blob = ((proc.stdout or "") + (proc.stderr or "")).strip()
    lines = blob.splitlines()
    return lines[-1] if lines else ""


# --- the tool exists and is dependency-free ---------------------------------
import scaffold  # noqa: E402

for required in ("scaffold.py", "README.md", "LICENSE", ".gitignore"):
    ok("repo.has_%s" % required.replace(".", "_"),
       os.path.exists(os.path.join(HERE, required)), "missing %s" % required)

raw = io.open(os.path.join(HERE, "scaffold.py"), encoding="utf-8").read()
for banned in ("import requests", "import numpy", "import pandas",
               "import yaml", "import click"):
    ok("scaffold.no_%s" % banned.replace(" ", "_").replace("import_", ""),
       banned not in raw, "third-party dependency crept in: %s" % banned)

ok("scaffold.stdlib_only_helpers",
   all(mod in raw for mod in ("import argparse", "import subprocess",
                              "import tempfile")),
   "expected stdlib helpers missing")

# --- every defence is really shipped as executable assertions ---------------
DEFENCE_NAMES = ("money", "units", "alias", "stdout", "evidence")
eq("scaffold.lists_five_defences", len(scaffold.DEFENCES), 5)
eq("scaffold.defence_keys", tuple(d[0] for d in scaffold.DEFENCES),
   DEFENCE_NAMES)

tmpl = scaffold.EVAL
for name in DEFENCE_NAMES:
    ok("template.defence_%s_is_asserted" % name,
       ('--- defence' in tmpl) and (name in tmpl),
       "defence %s is documented but not tested in the generated suite" % name)

# every defence incident description must be non-empty prose
for key, desc in scaffold.DEFENCES:
    ok("scaffold.defence_%s_documented" % key,
       isinstance(desc, str) and len(desc) > 40,
       "defence %s needs the incident behind it" % key)

# --- generating a project works, twice (idempotent) -------------------------
tmp = tempfile.mkdtemp(prefix="h48_eval_")
try:
    root, wrote = scaffold.create("AlphaProj", tmp, author="tester")
    eq("generate.file_count", len(wrote), 9)
    for rel in ("eval.py", "README.md", "README.zh.md", "LICENSE",
                ".gitignore", ".github/workflows/ci.yml",
                "alphaproj/__init__.py", "alphaproj/core.py",
                "alphaproj/__main__.py"):
        ok("generate.has_%s" % rel.replace("/", "_").replace(".", "_"),
           os.path.exists(os.path.join(root, rel)), "missing %s" % rel)

    eq("generate.pkg_name_lowercased", os.path.isdir(
        os.path.join(root, "alphaproj")), True)

    # the generated project is born green -- this is the core promise
    proc = _run(["eval.py"], cwd=root)
    ok("generate.eval_is_green", proc.returncode == 0, _tail(proc))
    counts = [tok for tok in _tail(proc).split() if tok.isdigit()]
    ok("generate.eval_has_assertions",
       bool(counts) and int(counts[0]) >= 30,
       "expected >=30 seed assertions, got %r" % _tail(proc))

    # hostile locale must not break the generated project
    env = {"LC_ALL": "C", "LANG": "C"}
    env_data = dict(env)
    proc_hostile = _run(["eval.py"], cwd=root, env=env_data)
    ok("generate.eval_green_hostile_locale", proc_hostile.returncode == 0,
       _tail(proc_hostile))
    eq("generate.same_count_hostile_locale", _tail(proc_hostile),
       _tail(proc))

    # generated CLI must not crash on a non-UTF-8 console
    proc_cli = _run(["-m", "alphaproj"], cwd=root,
                    env={"PYTHONIOENCODING": "ascii", "LC_ALL": "C"})
    ok("generate.cli_survives_ascii_stdout", proc_cli.returncode == 0,
       _tail(proc_cli))

    # regeneration is idempotent: same files, same result
    before = sorted(wrote)
    scaffold.create("AlphaProj", tmp, author="tester", force=True)
    after = sorted(scaffold.create("AlphaProj", tmp, author="tester",
                                   force=True)[1])
    eq("generate.idempotent_file_set", after, before)
    proc2 = _run(["eval.py"], cwd=root)
    eq("generate.idempotent_still_green", proc2.returncode, 0)

    # refusing to clobber without --force
    try:
        scaffold.create("AlphaProj", tmp, author="tester")
        ok("generate.refuses_without_force", False, "no error raised")
    except SystemExit:
        ok("generate.refuses_without_force", True)

    # money helper: halfcent must round HALF UP (the actual incident)
    sys.path.insert(0, root)
    import alphaproj.core as core  # noqa: E402

    eq("gen.money_half_cent_rounds_up", core.parse_money("0.005"), 1)
    eq("gen.money_never_float", isinstance(core.parse_money("1.00"), float),
       False)
    eq("gen.units_missing_rate_fails",
       core.Quantity(1, "CNY").converted("USD", {}), None)
    eq("gen.unknown_has_no_evidence", core.Finding("x", core.UNKNOWN, ()).evidence,
       ())
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# --- selfcheck reports PASS -------------------------------------------------
proc = _run(["scaffold.py", "--selfcheck"])
ok("selfcheck.passes", proc.returncode == 0, _tail(proc))
blob = (proc.stdout or "") + (proc.stderr or "")
ok("selfcheck.reports_pass", "SELFCHECK PASS" in blob, "no PASS verdict")

# --- README claims are grounded --------------------------------------------
readme = io.open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
ok("readme.mentions_selfcheck", "scaffold.py --selfcheck" in readme)
ok("readme.mentions_five_defences", "alias" in readme and "stdout" in readme)
ok("readme.documents_create_usage", "scaffold.py MyProject" in readme,
   "README must show how to create a project")
ok("readme.documents_author_flag", "--author" in readme)

# --- report (ASCII-only so this suite survives LC_ALL=C) --------------------
sys.stderr.write("%d passed, %d failed\n" % (len(PASSED), len(FAILED)))
for line in FAILED:
    sys.stderr.write("  FAIL %s\n" % line)
sys.exit(1 if FAILED else 0)
