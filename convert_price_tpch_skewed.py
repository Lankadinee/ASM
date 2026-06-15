"""Convert the PRICE-style filtered TPC-H skewed workload to ASM format.

Input format (||-delimited, 3 fields):
    <SQL>||<true_card>||@q<int>-t<int>@

Each TPC-H query has no aliases; FROM uses table names directly.
Predicates use the canonical column prefixes (c_/o_/l_/p_/ps_/s_/n_/r_), so we
add a `<table>.` prefix before each column reference. We also rewrite
`DATE 'YYYY-MM-DD'` to `'YYYY-MM-DD'` so ASM's value parser strips the quotes
and compares lexicographically against the YYYY-MM-DD strings written into
table0.csv from the parquet datetime64 columns.

Outputs (under <OUT_DIR>/):
    all_queries.pkl                  : {qname: rewritten_sql}
    all_sub_plan_queries_str.pkl     : {qname: list[(left_table, right_str)]}
    predicate/<qname>.pkl            : {table: (table, " filters_with_AND ", set(join_cols))}
    true_cardinalities.csv           : qname,true_card
"""
from __future__ import annotations

import os
import pickle
import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path

WORKLOAD = (
    "/home/student.unimelb.edu.au/lrathuwadu/cardinality-estimation-data/"
    "original_data/tpch_skewed/queries/tpch_template_workload_filtered.sql"
)
OUT_DIR = Path("/home/student.unimelb.edu.au/lrathuwadu/ASM/tpch_skewed_queries")
OUT_DIR.mkdir(parents=True, exist_ok=True)
(OUT_DIR / "predicate").mkdir(parents=True, exist_ok=True)

PREFIX_TO_TABLE = [
    ("ps_", "partsupp"),
    ("c_", "customer"),
    ("o_", "orders"),
    ("l_", "lineitem"),
    ("p_", "part"),
    ("s_", "supplier"),
    ("n_", "nation"),
    ("r_", "region"),
]


def column_to_table(col_name: str) -> str:
    cl = col_name.lower()
    for prefix, table in PREFIX_TO_TABLE:
        if cl.startswith(prefix):
            return table
    raise ValueError(f"unknown column prefix: {col_name!r}")


def add_table_prefix(predicate: str, present_tables: set[str]) -> str:
    """Replace bare column references with `<table>.<col>` (TPC-H prefix conv)."""
    DATE_RE = re.compile(r"\bDATE\s+('[^']+')")
    s = DATE_RE.sub(lambda m: m.group(1), predicate)

    out = []
    i = 0
    in_quote = False
    while i < len(s):
        ch = s[i]
        if ch == "'":
            in_quote = not in_quote
            out.append(ch)
            i += 1
            continue
        if in_quote:
            out.append(ch)
            i += 1
            continue
        m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", s[i:])
        if m:
            tok = m.group(0)
            tl = tok.lower()
            if tl.upper() in {"AND", "OR", "NOT", "IN", "LIKE", "NULL", "IS", "BETWEEN"}:
                out.append(tok)
                i += len(tok)
                continue
            try:
                table = column_to_table(tl)
            except ValueError:
                out.append(tok)
                i += len(tok)
                continue
            if table not in present_tables:
                raise ValueError(
                    f"predicate references {table!r} which isn't in FROM: {predicate!r}"
                )
            out.append(f"{table}.{tl}")
            i += len(tok)
        else:
            out.append(ch)
            i += 1
    return "".join(out)


JOIN_PRED_RE = re.compile(r"^\s*(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)\s*$")


def parse_from(sql: str) -> list[str]:
    m = re.search(r"\bFROM\b(.*?)\bWHERE\b", sql, re.IGNORECASE | re.DOTALL)
    assert m, f"no FROM..WHERE: {sql}"
    raw = m.group(1)
    items = [x.strip() for x in raw.split(",")]
    return [it.split()[0].strip().lower() for it in items]


def parse_where(sql: str) -> list[str]:
    m = re.search(r"\bWHERE\b(.*?);?\s*$", sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    body = m.group(1).strip().rstrip(";").strip()
    return [p.strip() for p in re.split(r"\s+AND\s+", body, flags=re.IGNORECASE) if p.strip()]


def split_joins_filters(conds, tables_set):
    joins, filters = [], []
    for c in conds:
        m = JOIN_PRED_RE.match(c)
        if m:
            t1, _, t2, _ = m.groups()
            if t1.lower() in tables_set and t2.lower() in tables_set:
                joins.append(c)
                continue
        filters.append(c)
    return joins, filters


def chain_for(als: tuple[str, ...]) -> list[tuple[str, str]]:
    """Generate ASM left-deep sub-plan chain for all 2..N subsets of als."""
    als_sorted = sorted(als)
    chain = []
    cached = set()
    for k in range(2, len(als_sorted) + 1):
        for combo in combinations(als_sorted, k):
            combo_list = list(combo)
            if k == 2:
                left, right = combo_list[-1], combo_list[0]
            else:
                chosen = None
                for i in range(k - 1, -1, -1):
                    cand_left = combo_list[i]
                    cand_right = " ".join([a for j, a in enumerate(combo_list) if j != i])
                    if cand_right in cached:
                        chosen = (cand_left, cand_right)
                        break
                assert chosen is not None, f"no cache hit for {combo_list}"
                left, right = chosen
            chain.append((left, right))
            cached.add(" ".join(combo_list))
    return chain


def build_predicate_dict(tables: list[str], joins: list[str], filters: list[str]):
    join_cols = {t: set() for t in tables}
    for c in joins:
        m = JOIN_PRED_RE.match(c)
        t1, c1, t2, c2 = m.groups()
        join_cols[t1.lower()].add(c1.lower())
        join_cols[t2.lower()].add(c2.lower())

    table_filters = defaultdict(list)
    for f in filters:
        m = re.match(r"^\s*([A-Za-z_]\w*)\.", f)
        if not m:
            continue
        table_filters[m.group(1).lower()].append(f)

    pred = {}
    for t in tables:
        fs = table_filters.get(t, [])
        ps = " " + " AND ".join(fs) + " " if fs else ""
        pred[t] = (t, ps, set(join_cols[t]))
    return pred


def build_rewritten_sql(tables: list[str], joins: list[str], filters: list[str]) -> str:
    body = " AND ".join(joins + filters)
    return f"SELECT COUNT(*) FROM {', '.join(tables)} WHERE {body}"


def main():
    with open(WORKLOAD) as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    all_queries = {}
    all_sub_plans = {}
    true_cards = []

    for ln in lines:
        parts = ln.split("||")
        assert len(parts) == 3, f"unexpected line: {ln!r}"
        sql, true_card, tag = parts
        m = re.search(r"@(q\d+)-", tag)
        assert m, f"no qid tag: {tag!r}"
        qname = m.group(1)

        tables = parse_from(sql)
        tables_set = set(tables)
        conds = parse_where(sql)
        joins, raw_filters = split_joins_filters(conds, tables_set)
        prefixed_filters = [add_table_prefix(f, tables_set) for f in raw_filters]
        prefixed_joins = []
        for j in joins:
            mj = JOIN_PRED_RE.match(j)
            t1, c1, t2, c2 = mj.groups()
            prefixed_joins.append(f"{t1.lower()}.{c1.lower()} = {t2.lower()}.{c2.lower()}")

        new_sql = build_rewritten_sql(tables, prefixed_joins, prefixed_filters)
        all_queries[qname] = new_sql

        chain = chain_for(tuple(tables))
        all_sub_plans[qname] = chain

        pred = build_predicate_dict(tables, prefixed_joins, prefixed_filters)
        with open(OUT_DIR / "predicate" / f"{qname}.pkl", "wb") as f:
            pickle.dump(pred, f, pickle.HIGHEST_PROTOCOL)

        true_cards.append((qname, int(true_card)))

    with open(OUT_DIR / "all_queries.pkl", "wb") as f:
        pickle.dump(all_queries, f, pickle.HIGHEST_PROTOCOL)
    with open(OUT_DIR / "all_sub_plan_queries_str.pkl", "wb") as f:
        pickle.dump(all_sub_plans, f, pickle.HIGHEST_PROTOCOL)
    with open(OUT_DIR / "true_cardinalities.csv", "w") as f:
        f.write("qname,true_card\n")
        for q, c in true_cards:
            f.write(f"{q},{c}\n")

    print(f"wrote {len(all_queries)} queries to {OUT_DIR}")
    print(f"sub-plans total: {sum(len(v) for v in all_sub_plans.values())}")
    print("first 3 rewritten queries:")
    for q in list(all_queries)[:3]:
        print(f"  {q}: {all_queries[q]}")


if __name__ == "__main__":
    main()
