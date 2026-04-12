"""Run only PG and optimal E2E for a dataset."""
import sys
import datetime
sys.path.insert(0, "/home/student.unimelb.edu.au/lrathuwadu/PRICE")
from benchmark.e2e import get_test_set_e2e_time

DB_HOST = "localhost"
DB_PORT = 5456
DB_USER = "postgres"
DB_PWD = "postgres"

dataset = sys.argv[1]
test_set_file = f"/home/student.unimelb.edu.au/lrathuwadu/ASM/results/{dataset}_perror_input.sql"

print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
print(f"dataset={dataset}")

print("\n=== PG native ===")
pg_times = get_test_set_e2e_time(test_set_file, dataset, "pg",
                                  db_host=DB_HOST, db_user=DB_USER,
                                  db_user_pwd=DB_PWD, db_port=DB_PORT)
print(f"PG total: {sum(pg_times):.2f}s")

print("\n=== Optimal (true card) ===")
opt_times = get_test_set_e2e_time(test_set_file, dataset, "optimal",
                                   db_host=DB_HOST, db_user=DB_USER,
                                   db_user_pwd=DB_PWD, db_port=DB_PORT)
print(f"Optimal total: {sum(opt_times):.2f}s")

print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
