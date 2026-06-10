"""Timeout helpers for flood-fill sample processing."""

from __future__ import annotations


class SampleTimeoutError(Exception):
    """Raised when processing exceeds the configured time limit."""


def raise_sample_timeout(signum, frame):
    raise SampleTimeoutError("Processing time exceeded")
