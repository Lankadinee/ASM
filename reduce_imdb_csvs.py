"""Produce JOB-light reduced CSVs from raw IMDB CSVs.

Uses csv module with escapechar='\\' (POSIX style) and drops rows where any
target column fails to parse as an integer. This avoids the mixed-type
garbage that pandas produces when note fields contain embedded quotes or
commas.
"""
import os
import csv

RAW = "/home/student.unimelb.edu.au/lrathuwadu/imdb_data/csv"
OUT = "/home/student.unimelb.edu.au/lrathuwadu/ASM/datasets/imdb"

# raw column count per table
NCOLS = {
    "title": 12,
    "movie_info": 5,
    "movie_info_idx": 5,
    "cast_info": 7,
    "movie_keyword": 3,
    "movie_companies": 5,
}

# (raw_col_index, out_name) for each kept column
KEEP = {
    "title":           [(0, "id"),       (3, "kind_id"),        (4, "production_year")],
    "movie_info":      [(1, "movie_id"), (2, "info_type_id")],
    "movie_info_idx":  [(1, "movie_id"), (2, "info_type_id")],
    "cast_info":       [(2, "movie_id"), (6, "role_id")],
    "movie_keyword":   [(1, "movie_id"), (2, "keyword_id")],
    "movie_companies": [(1, "movie_id"), (2, "company_id"), (3, "company_type_id")],
}

os.makedirs(OUT, exist_ok=True)

# Remove stale symlinks / files
for f in os.listdir(OUT):
    p = os.path.join(OUT, f)
    if os.path.islink(p) or (os.path.isfile(p) and f.endswith(".csv")):
        os.unlink(p)

csv.field_size_limit(10**7)

for tbl, keep in KEEP.items():
    src = os.path.join(RAW, f"{tbl}.csv")
    dst = os.path.join(OUT, f"{tbl}.csv")
    n_raw = 0
    n_out = 0
    n_skip = 0
    ncols = NCOLS[tbl]
    idxs = [i for i, _ in keep]
    header = [name for _, name in keep]
    print(f"reducing {tbl} ({ncols} raw cols -> {len(keep)} kept) ...")
    with open(src, "r", encoding="utf-8", errors="replace") as fi, \
         open(dst, "w", encoding="utf-8", newline="") as fo:
        reader = csv.reader(fi, quotechar='"', escapechar='\\',
                            doublequote=False, strict=False)
        writer = csv.writer(fo)
        writer.writerow(header)
        for row in reader:
            n_raw += 1
            if len(row) != ncols:
                n_skip += 1
                continue
            out_row = []
            bad = False
            for i in idxs:
                v = row[i].strip()
                if v == "":
                    # null integer — drop row (join cols can't be null anyway)
                    bad = True
                    break
                try:
                    int(v)
                except ValueError:
                    bad = True
                    break
                out_row.append(v)
            if bad:
                n_skip += 1
                continue
            writer.writerow(out_row)
            n_out += 1
    print(f"  {tbl}: {n_out}/{n_raw} rows kept ({n_skip} skipped)")

print("done")
