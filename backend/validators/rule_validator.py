"""Ownership + status-flow adjacency + arg/schema checks — the real gate.

Pure functions, no side effects: given a proposed tool call + current
state, return allow/deny + reason.
"""
