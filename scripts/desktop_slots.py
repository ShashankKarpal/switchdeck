#!/usr/bin/env python3
"""Build, remove or report the Desktop app slot shims.

    scripts/desktop_slots.py build [--slots 1 2]   compile and install one shim
                                                    per slot into ~/Applications
    scripts/desktop_slots.py status                 what is installed, what is running
    scripts/desktop_slots.py remove                 delete marked shims only

Slot labels come from local_settings.py (SHORT_LABELS); defaults are the
slot numbers. Needs the Xcode command line tools (swiftc) for build. Any
interpreter works; nothing here imports rumps.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import desktop_slots as ds  # noqa: E402

SHORT_LABELS = {1: "1", 2: "2"}
try:
    import local_settings as _ls  # noqa: E402
    SHORT_LABELS = getattr(_ls, "SHORT_LABELS", SHORT_LABELS)
except ImportError:
    pass


def _label(slot):
    return str(SHORT_LABELS.get(slot, SHORT_LABELS.get(str(slot), slot)))


def cmd_build(args):
    slots = [int(s) for s in args.slots] if args.slots else sorted(
        int(k) for k in SHORT_LABELS)
    for slot in slots:
        path = ds.build_shim(slot, _label(slot))
        print("built slot %d -> %s (profile %s)" % (slot, path, ds.profile_dir(slot)))
    return 0


def cmd_status(_args):
    entries = ds.status()
    if not entries:
        print("no shims installed")
        return 1
    for e in entries:
        print("slot %d  %s  %s  profile=%s" % (
            e["slot"], "running" if e["running"] else "idle", e["path"], e["profile"]))
    return 0


def cmd_remove(_args):
    removed = ds.remove_shims()
    for p in removed:
        print("removed %s" % p)
    print("%d shim(s) removed; profile folders untouched" % len(removed))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--slots", nargs="*")
    b.set_defaults(fn=cmd_build)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("remove").set_defaults(fn=cmd_remove)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except (RuntimeError, ValueError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
