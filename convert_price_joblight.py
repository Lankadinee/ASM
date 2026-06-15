"""Convert PRICE JOB-light workload to ASM's pkl format.

PRICE `workloads.sql` has 766 lines, each a sub-query annotated with
`@parent_id-sub_id@` and (for sub-plans) a `/* (alias, ...) */` comment.
Group lines by parent id; for each parent we emit one ASM "query" whose
sub_plan list is all the alias subsets that appear in that parent's group.
"""
import os
import pickle
import re
from collections import defaultdict

PRICE_WORKLOAD = "/home/student.unimelb.edu.au/lrathuwadu/cardinality-estimation-data/processed_data/imdb/workloads.sql"
OUT_DIR = "/home/student.unimelb.edu.au/lrathuwadu/ASM/jobl_queries"
PRED_DIR = f"{OUT_DIR}/predicate"

os.makedirs(PRED_DIR, exist_ok=True)

# alias (as used in PRICE) -> table name + join columns
ALIAS_TABLE = {
    "imdb_t":   ("title",           {"id"}),
    "imdb_mc":  ("movie_companies", {"movie_id"}),
    "imdb_mii": ("movie_info_idx",  {"movie_id"}),
    "imdb_mi":  ("movie_info",      {"movie_id"}),
    "imdb_mk":  ("movie_keyword",   {"movie_id"}),
    "imdb_ci":  ("cast_info",       {"movie_id"}),
}


def parse_from_clause(sql):
    """Return list of (table, alias) for all items in FROM."""
    m = re.search(r"\bFROM\b(.*?)\bWHERE\b", sql, re.IGNORECASE | re.DOTALL)
    assert m, f"no FROM..WHERE in: {sql}"
    raw = m.group(1)
    items = [x.strip() for x in raw.split(",")]
    out = []
    for it in items:
        # 'title as imdb_t' OR 'title imdb_t'
        parts = re.split(r"\s+as\s+|\s+", it, flags=re.IGNORECASE)
        parts = [p for p in parts if p]
        assert len(parts) == 2, f"bad FROM item: {it!r}"
        tbl, al = parts[0], parts[1]
        out.append((tbl.lower(), al.lower()))
    return out


def parse_where(sql):
    """Return list of condition strings from WHERE clause."""
    m = re.search(r"\bWHERE\b(.*?);?\s*$", sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    body = m.group(1).strip().rstrip(";").strip()
    parts = re.split(r"\s+and\s+", body, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]
    # strip surrounding parentheses
    cleaned = []
    for p in parts:
        while p.startswith("(") and p.endswith(")"):
            # only strip when the parens match at top level
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
    joins = []
    filters = []
    for c in conds:
        m = JOIN_RE.match(c)
        if m:
            joins.append(c)
        else:
            filters.append(c)
    return joins, filters


def build_predicate_dict(sql):
    from_items = parse_from_clause(sql)
    alias_to_table = {al: tbl for tbl, al in from_items}
    conds = parse_where(sql)
    joins, filters = split_joins_filters(conds)

    # per-alias join columns (extracted from join conditions)
    alias_join_cols = {al: set() for _, al in from_items}
    for c in joins:
        m = JOIN_RE.match(c)
        a1, c1, a2, c2 = m.groups()
        alias_join_cols[a1.lower()].add(c1.lower())
        alias_join_cols[a2.lower()].add(c2.lower())

    # per-alias filter predicates (joined with AND, same format as parent)
    alias_filters = defaultdict(list)
    for f in filters:
        # find which alias owns this filter (prefix before '.')
        m2 = re.match(r"\s*(\w+)\.", f)
        if not m2:
            continue
        alias_filters[m2.group(1).lower()].append(f)

    pred = {}
    for al in alias_to_table:
        tbl = alias_to_table[al]
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
    # strip /* ... */ comment to get plain SQL
    sql_clean = SUBPLAN_COMMENT_RE.sub("", sql).strip()
    # ASM's parser splits WHERE body by " AND " (uppercase). Parent lines use
    # lowercase " and " — normalise so both parent and sub-plan forms parse.
    sql_clean = re.sub(r"\s+and\s+", " AND ", sql_clean, flags=re.IGNORECASE)
    # alias set
    sub_m = SUBPLAN_COMMENT_RE.search(sql)
    if sub_m:
        aliases = tuple(sorted(a.strip().lower() for a in sub_m.group(1).split(",")))
    else:
        # parent — use FROM clause
        try:
            froms = parse_from_clause(sql_clean)
            aliases = tuple(sorted(al for _, al in froms))
        except Exception:
            return None
    return dict(idx=None, sql=sql_clean, aliases=aliases, pid=pid, sid=sid,
                true_card=int(true_card), pg_card=int(pg_card))


def main():
    with open(PRICE_WORKLOAD) as f:
        lines = [ln for ln in f if ln.strip()]

    parsed = []
    for i, ln in enumerate(lines):
        p = parse_line(ln)
        if p is None:
            print(f"skip line {i}: {ln[:60]}")
            continue
        p["idx"] = i
        parsed.append(p)

    print(f"parsed {len(parsed)} of {len(lines)} lines")

    # group by parent id
    groups = defaultdict(list)
    for p in parsed:
        groups[p["pid"]].append(p)

    all_queries = {}
    all_sub_plan_queries_str = {}
    line_to_qname_and_spidx = {}  # idx -> (qname, sub_plan_index) where index == output position in ASM result file

    for pid in sorted(groups.keys()):
        grp = groups[pid]
        # find the parent line (full query — the one with most aliases)
        grp_sorted = sorted(grp, key=lambda x: (len(x["aliases"]), x["sid"]))
        full_line = grp_sorted[-1]  # largest alias set
        parent_sql = full_line["sql"]  # use a well-formed SQL — prefer one with the full alias set
        # All alias subsets in this group, deduped, sorted by size ascending
        seen_sets = []
        for p in grp_sorted:
            als = p["aliases"]
            if len(als) < 2:
                continue  # ASM's sub_plan list starts at size 2
            if als not in seen_sets:
                seen_sets.append(als)
        # seen_sets is already size-ascending because grp_sorted was

        # Build sub_plan_list: list of (left_alias, right_aliases_str) in order
        # For a subset S of size k, pick left = alphabetically last, right = sorted(S-{left}) joined by space.
        sub_plan_list = []
        cached_keys = set()
        for als in seen_sets:
            als_sorted = sorted(als)
            if len(als_sorted) == 2:
                # order as (last, first) — either works
                left = als_sorted[-1]
                right = als_sorted[0]
            else:
                left = als_sorted[-1]
                right_aliases = als_sorted[:-1]
                right = " ".join(right_aliases)
                # ensure right is cached
                if right not in cached_keys:
                    # fallback: try other choices of left
                    found = False
                    for cand_left_idx in range(len(als_sorted) - 1, -1, -1):
                        cand_left = als_sorted[cand_left_idx]
                        cand_right = " ".join(
                            [a for j, a in enumerate(als_sorted) if j != cand_left_idx]
                        )
                        if cand_right in cached_keys:
                            left = cand_left
                            right = cand_right
                            found = True
                            break
                    if not found:
                        raise RuntimeError(
                            f"parent {pid}: no cached right for {als_sorted}. cached={cached_keys}"
                        )
            sub_plan_list.append((left, right))
            cached_keys.add(" ".join(als_sorted))

        qname = f"q{pid}"
        all_queries[qname] = parent_sql
        all_sub_plan_queries_str[qname] = sub_plan_list

        # save predicate pkl (based on parent / full SQL with all filters)
        pred, alias_to_table = build_predicate_dict(parent_sql)
        with open(f"{PRED_DIR}/{qname}.pkl", "wb") as f:
            pickle.dump(pred, f, pickle.HIGHEST_PROTOCOL)

        # map each PRICE line to (qname, sub_plan_index_in_list)
        alias_set_to_spidx = {als: i for i, als in enumerate(seen_sets)}
        for p in grp:
            if len(p["aliases"]) < 2:
                continue  # skip single-table — ASM doesn't estimate these
            spidx = alias_set_to_spidx[p["aliases"]]
            line_to_qname_and_spidx[p["idx"]] = (qname, spidx, p["true_card"])

    with open(f"{OUT_DIR}/all_queries.pkl", "wb") as f:
        pickle.dump(all_queries, f, pickle.HIGHEST_PROTOCOL)
    with open(f"{OUT_DIR}/all_sub_plan_queries_str.pkl", "wb") as f:
        pickle.dump(all_sub_plan_queries_str, f, pickle.HIGHEST_PROTOCOL)
    with open(f"{OUT_DIR}/line_to_qname_spidx.pkl", "wb") as f:
        pickle.dump(line_to_qname_and_spidx, f, pickle.HIGHEST_PROTOCOL)

    print(f"wrote {len(all_queries)} parent queries")
    print(f"wrote {sum(len(v) for v in all_sub_plan_queries_str.values())} sub-plans")
    print(f"mapped {len(line_to_qname_and_spidx)} PRICE lines")

    # Sanity: check predicates round-trip
    any_q = next(iter(all_queries))
    with open(f"{PRED_DIR}/{any_q}.pkl", "rb") as f:
        d = pickle.load(f)
    print(f"sample predicate ({any_q}): {d}")
    print(f"sample sub_plan_list ({any_q}): {all_sub_plan_queries_str[any_q]}")


if __name__ == "__main__":
    main()
