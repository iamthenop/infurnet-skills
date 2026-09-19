#!/usr/bin/env python3
"""Shared Git operations for the skill-installer scripts: checkout
inspection, tree acquisition, and remote-reference retrieval.

This is a shared implementation module, not a checker or a command-line
entry point. Callers retain responsibility for selecting destinations,
cleanup, and interpreting results; this module only runs the Git commands
and reports what they observed.
"""
import subprocess


def _run(args):
    return subprocess.run(args, capture_output=True, text=True)


# --- checkout inspection ---------------------------------------------------


def inspect_checkout(path, expected_origin, expected_commit):
    """The observed state of a checkout at `path` against an expected
    origin URL and full commit — the one implementation of Git checkout
    inspection shared by every caller that needs to know whether a
    checkout matches a declared identity. A failed Git command is never
    interpreted as a successful, matching inspection.

    Returns a dict:
      exists          -- False if `path` has no .git; every other field is
                          then a placeholder ("no" match, no observed value)
      head            -- the checkout's HEAD commit, or None if unreadable
      head_matches    -- head == expected_commit
      detached        -- True if HEAD is a detached commit, False if it is
                          attached to a branch
      branch_name     -- the attached branch's ref name, or None if detached
      clean           -- True/False if known, None if `git status` itself
                          failed (distinct from a known-dirty tree)
      status_error    -- the failed status command's stderr, or None
      origin          -- the checkout's origin URL, or None if unreadable
      origin_matches  -- origin == expected_origin
    """
    if not (path / ".git").exists():
        return {
            "exists": False, "head": None, "head_matches": False,
            "detached": False, "branch_name": None,
            "clean": False, "status_error": None,
            "origin": None, "origin_matches": False,
        }

    head_proc = _run(["git", "-C", str(path), "rev-parse", "HEAD"])
    head = head_proc.stdout.strip() if head_proc.returncode == 0 else None
    head_matches = head is not None and head == expected_commit

    detached_proc = _run(["git", "-C", str(path), "symbolic-ref", "-q", "HEAD"])
    # Exit 0 means HEAD IS a symbolic ref, i.e. attached to a branch.
    detached = detached_proc.returncode != 0
    branch_name = detached_proc.stdout.strip() if not detached else None

    status_proc = _run(["git", "-C", str(path), "status", "--porcelain"])
    if status_proc.returncode != 0:
        clean, status_error = None, status_proc.stderr.strip()
    else:
        clean, status_error = not status_proc.stdout.strip(), None

    # `git config --get`, not `git remote get-url` (which expands any
    # configured insteadOf rewrite): this must report the checkout's raw
    # configured origin, to compare against the declared source exactly as
    # production code would have written it — a transport-only rewrite
    # (e.g. redirecting a GitHub URL to a local fixture in tests) must
    # never make a correctly-configured checkout look mismatched.
    origin_proc = _run(["git", "-C", str(path), "config", "--get", "remote.origin.url"])
    origin = origin_proc.stdout.strip() if origin_proc.returncode == 0 else None
    origin_matches = origin is not None and origin == expected_origin

    return {
        "exists": True, "head": head, "head_matches": head_matches,
        "detached": detached, "branch_name": branch_name,
        "clean": clean, "status_error": status_error,
        "origin": origin, "origin_matches": origin_matches,
    }


# --- tree acquisition --------------------------------------------------


def acquire_tree(repo_url, sha, dest):
    """Clones repo_url (no checkout) into the already-existing, empty
    directory `dest`, then checks out `sha` there. Selects no destination
    and performs no cleanup — the caller owns both."""
    subprocess.run(["git", "clone", "--quiet", "--no-checkout", repo_url, str(dest)],
                   check=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "--quiet", sha], check=True)


# --- remote-reference retrieval -----------------------------------------


def ls_remote(*args):
    """[(sha, name), ...] for each ref line `git ls-remote <args>` reports.
    Raises RuntimeError, naming the command and its stderr, on a nonzero
    exit — a failed command must never be mistaken for a discovery result
    that simply found no matching refs."""
    result = _run(["git", "ls-remote", *args])
    if result.returncode != 0:
        raise RuntimeError(f"git ls-remote {' '.join(args)} failed: "
                          f"{result.stderr.strip()}")
    pairs = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        sha, name = line.split("\t", 1)
        pairs.append((sha, name))
    return pairs
