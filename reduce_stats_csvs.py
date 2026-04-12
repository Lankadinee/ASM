"""Copy STATS CSVs into ASM/datasets/stats/ with lowercase headers.

Dates (CreationDate, Date) are converted from ISO timestamp strings to Unix
epoch integers so they're comparable with PRICE's integer date predicates.
"""
import os
import csv
import datetime as dt

SRC = "/home/student.unimelb.edu.au/lrathuwadu/stats_data/End-to-End-CardEst-Benchmark-master/datasets/stats_simplified"
OUT = "/home/student.unimelb.edu.au/lrathuwadu/ASM/datasets/stats"

DATE_COLS = {"CreationDate", "Date"}

os.makedirs(OUT, exist_ok=True)
# Clean any stale files (but keep per-table subdirs that may be reused)
for f in os.listdir(OUT):
    p = os.path.join(OUT, f)
    if os.path.isfile(p) and f.endswith(".csv"):
        os.unlink(p)


def to_epoch(s):
    s = s.strip()
    if not s:
        return ""
    # Format seen in the raw file: 'YYYY-MM-DD HH:MM:SS'
    try:
        t = dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            t = dt.datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            return ""
    return str(int(t.timestamp()))


for name in os.listdir(SRC):
    if not name.endswith(".csv"):
        continue
    src = os.path.join(SRC, name)
    dst = os.path.join(OUT, name)
    with open(src, "r", encoding="utf-8", errors="replace") as fi:
        reader = csv.reader(fi)
        header = next(reader)
        lower = [h.lower() for h in header]
        date_idxs = [i for i, h in enumerate(header) if h in DATE_COLS]
        out_rows = 0
        with open(dst, "w", encoding="utf-8", newline="") as fo:
            writer = csv.writer(fo)
            writer.writerow(lower)
            for row in reader:
                if len(row) != len(header):
                    continue
                for i in date_idxs:
                    row[i] = to_epoch(row[i])
                writer.writerow(row)
                out_rows += 1
        print(f"{name}: header {header} -> {lower}; date_idxs={date_idxs}; rows={out_rows}")

print("done")
