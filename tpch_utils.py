"""Utilities for the tpch_skewed workload (mirrors stats_utils / imdb_utils)."""


def qname_to_qindex(qname):
    """Map a query name like 'q47' to its integer index 47."""
    assert qname.startswith('q'), f"unexpected qname: {qname!r}"
    return int(qname[1:])
