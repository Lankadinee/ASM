"""Convert PRICE STATS-CEB workload to ASM format.

PRICE's STATS workload uses aliases like `st_b`, `st_u`, `st_p`, ... and
lowercase column names. Dates are already Unix-epoch ints in both the
predicates and the reduced CSVs, so no conversion is needed here.
"""
import os
import pickle
import re
from collections import defaultdict

PRICE_WORKLOAD = "/home/student.unimelb.edu.au/lrathuwadu/PRICE/datas/workloads/test/stats/workloads.sql"
BATCHED_DIR = "/home/student.unimelb.edu.au/lrathuwadu/ASM/stats_jobl_queries"
PERLINE_DIR = "/home/student.unimelb.edu.au/lrathuwadu/ASM/stats_perline_queries"

os.makedirs(f"{BATCHED_DIR}/predicate", exist_ok=True)
os.makedirs(f"{PERLINE_DIR}/predicate", exist_ok=True)

# alias (PRICE) -> table (lowercase to match ASM STATS schema)
ALIAS_TABLE = {
    "st_b":  "badges",
    "st_c":  "comments",
    "st_p":  "posts",
    "st_ph": "posthistory",
    "st_pl": "postlinks",
    "st_t":  "tags",
    "st_u":  "users",
    "st_v":  "votes",
}

# join columns per table (which columns participate in any schema relationship)
JOIN_COLS = {
    "badges":      {"userid"},
    "comments":    {"postid", "userid"},
    "posts":       {"id", "owneruserid"},
    "posthistory": {"postid", "userid"},
    "postlinks":   {"postid", "relatedpostid"},
    "tags":        {"excerptpostid"},
    "users":       {"id"},
    "votes":       {"postid", "userid"},
}


def parse_from_clause(sql):
    m = re.search(r"\bFROM\b(.*?)\bWHERE\b", sql, re.IGNORECASE | re.DOTALL)
    assert m, f"no FROM..WHERE in: {sql}"
    raw = m.group(1)
    items = [x.strip() for x in raw.split(",")]
    out = []
    for it in items:
        parts = re.split(r"\s+as\s+|\s+", it, flags=re.IGNORECASE)
        parts = [p for p in parts if p]
        assert len(parts) == 2, f"bad FROM item: {it!r}"
        tbl, al = parts[0], parts[1]
        out.append((tbl.lower(), al.lower()))
    return out


def parse_where(sql):
    m = re.search(r"\bWHERE\b(.*?);?\s*$", sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    body = m.group(1).strip().rstrip(";").strip()
    parts = re.split(r"\s+and\s+", body, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]
    cleaned = []
    for p in parts:
        while p.startswith("(") and p.endswith(")"):
            inner = p[1:-1]
            depth = 0
            ok = True
            for ch in inner:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth < 0:
                        ok = False
                        break
            if ok and depth == 0:
                p = inner.strip()
            else:
                break
        cleaned.append(p)
    return cleaned


JOIN_RE = re.compile(r"^\s*(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)\s*$")


def split_joins_filters(conds):
    joins, filters = [], []
    for c in conds:
        if JOIN_RE.match(c):
            joins.append(c)
        else:
            filters.append(c)
    return joins, filters


def build_predicate_dict(sql):
    from_items = parse_from_clause(sql)
    alias_to_table = {al: tbl for tbl, al in from_items}
    conds = parse_where(sql)
    joins, filters = split_joins_filters(conds)

    alias_join_cols = {al: set() for _, al in from_items}
    for c in joins:
        m = JOIN_RE.match(c)
        a1, c1, a2, c2 = m.groups()
        alias_join_cols[a1.lower()].add(c1.lower())
        alias_join_cols[a2.lower()].add(c2.lower())

    alias_filters = defaultdict(list)
    for f in filters:
        m2 = re.match(r"\s*(\w+)\.", f)
        if not m2:
            continue
        alias_filters[m2.group(1).lower()].append(f)

    pred = {}
    for al, tbl in alias_to_table.items():
        fs = alias_filters.get(al, [])
        pred_str = " " + " AND ".join(fs) + " " if fs else ""
        pred[al] = (tbl, pred_str, set(alias_join_cols[al]))
    return pred, alias_to_table


TAG_RE = re.compile(r"@(\d+)-(\d+)@")
SUBPLAN_COMMENT_RE = re.compile(r"/\*\s*\((.*?)\)\s*\*/")


def parse_line(line):
    parts = line.strip().split("||")
    if len(parts) < 4:
        return None
    sql, true_card, pg_card, tag = parts[0], parts[1], parts[2], parts[3]
    m = TAG_RE.search(tag)
    if not m:
        return None
    pid, sid = int(m.group(1)), int(m.group(2))
    sql_clean = SUBPLAN_COMMENT_RE.sub("", sql).strip()
    sql_clean = re.sub(r"\s+and\s+", " AND ", sql_clean, flags=re.IGNORECASE)
    sub_m = SUBPLAN_COMMENT_RE.search(sql)
    if sub_m:
        aliases = tuple(sorted(a.strip().lower() for a in sub_m.group(1).split(",")))
    else:
        try:
            froms = parse_from_clause(sql_clean)
            aliases = tuple(sorted(al for _, al in froms))
        except Exception:
            return None
    return dict(idx=None, sql=sql_clean, aliases=aliases, pid=pid, sid=sid,
                true_card=int(true_card), pg_card=int(pg_card))


def chain_for(als):
    from itertools import combinations
    als_sorted = sorted(als)
    M = len(als_sorted)
    chain = []
    cached = set()
    for k in range(2, M + 1):
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
                assert chosen is not None
                left, right = chosen
            chain.append((left, right))
            cached.add(" ".join(combo_list))
    return chain


def main():
    with open(PRICE_WORKLOAD) as f:
        lines = [ln for ln in f if ln.strip()]

    parsed = []
    for i, ln in enumerate(lines):
        p = parse_line(ln)
        if p is None:
            continue
        p["idx"] = i
        parsed.append(p)
    print(f"parsed {len(parsed)} of {len(lines)} lines")

    # ------- BATCHED (group by parent) -------
    groups = defaultdict(list)
    for p in parsed:
        groups[p["pid"]].append(p)

    all_queries_b = {}
    all_sub_plan_b = {}
    line_to_qname_b = {}

    for pid in sorted(groups.keys()):
        grp = groups[pid]
        grp_sorted = sorted(grp, key=lambda x: (len(x["aliases"]), x["sid"]))
        full_line = grp_sorted[-1]
        parent_sql = full_line["sql"]

        seen_sets = []
        for p in grp_sorted:
            if len(p["aliases"]) < 2:
                continue
            if p["aliases"] not in seen_sets:
                seen_sets.append(p["aliases"])

        chain = []
        cached = set()
        for als in seen_sets:
            als_sorted = sorted(als)
            if len(als_sorted) == 2:
                left, right = als_sorted[-1], als_sorted[0]
            else:
                chosen = None
                for i in range(len(als_sorted) - 1, -1, -1):
                    cand_left = als_sorted[i]
                    cand_right = " ".join([a for j, a in enumerate(als_sorted) if j != i])
                    if cand_right in cached:
                        chosen = (cand_left, cand_right)
                        break
                assert chosen is not None, f"parent {pid}: no cache for {als_sorted}"
                left, right = chosen
            chain.append((left, right))
            cached.add(" ".join(als_sorted))

        qname = f"q{pid}"
        all_queries_b[qname] = parent_sql
        all_sub_plan_b[qname] = chain

        pred, _ = build_predicate_dict(parent_sql)
        with open(f"{BATCHED_DIR}/predicate/{qname}.pkl", "wb") as f:
            pickle.dump(pred, f, pickle.HIGHEST_PROTOCOL)

        alias_set_to_idx = {als: i for i, als in enumerate(seen_sets)}
        for p in grp:
            if len(p["aliases"]) < 2:
                continue
            line_to_qname_b[p["idx"]] = (qname, alias_set_to_idx[p["aliases"]], p["true_card"])

    with open(f"{BATCHED_DIR}/all_queries.pkl", "wb") as f:
        pickle.dump(all_queries_b, f, pickle.HIGHEST_PROTOCOL)
    with open(f"{BATCHED_DIR}/all_sub_plan_queries_str.pkl", "wb") as f:
        pickle.dump(all_sub_plan_b, f, pickle.HIGHEST_PROTOCOL)
    with open(f"{BATCHED_DIR}/line_to_qname_spidx.pkl", "wb") as f:
        pickle.dump(line_to_qname_b, f, pickle.HIGHEST_PROTOCOL)
    print(f"batched: {len(all_queries_b)} queries, {sum(len(v) for v in all_sub_plan_b.values())} sub-plans, {len(line_to_qname_b)} lines mapped")

    # ------- PER-LINE (each PRICE line is its own standalone query) -------
    all_queries_p = {}
    all_sub_plan_p = {}
    line_to_qname_p = {}
    for p in parsed:
        if len(p["aliases"]) < 2:
            continue
        qname = f"l{p['idx']}"
        chain = chain_for(p["aliases"])
        all_queries_p[qname] = p["sql"]
        all_sub_plan_p[qname] = chain
        pred, _ = build_predicate_dict(p["sql"])
        with open(f"{PERLINE_DIR}/predicate/{qname}.pkl", "wb") as f:
            pickle.dump(pred, f, pickle.HIGHEST_PROTOCOL)
        line_to_qname_p[p["idx"]] = (qname, len(chain) - 1, p["true_card"])

    with open(f"{PERLINE_DIR}/all_queries.pkl", "wb") as f:
        pickle.dump(all_queries_p, f, pickle.HIGHEST_PROTOCOL)
    with open(f"{PERLINE_DIR}/all_sub_plan_queries_str.pkl", "wb") as f:
        pickle.dump(all_sub_plan_p, f, pickle.HIGHEST_PROTOCOL)
    with open(f"{PERLINE_DIR}/line_to_qname_spidx.pkl", "wb") as f:
        pickle.dump(line_to_qname_p, f, pickle.HIGHEST_PROTOCOL)
    print(f"per-line: {len(all_queries_p)} queries, {sum(len(v) for v in all_sub_plan_p.values())} sub-plans, {len(line_to_qname_p)} lines mapped")


if __name__ == "__main__":
    main()
