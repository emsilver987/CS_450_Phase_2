# NEW FILE (imported by conftest)
import io, os, time, zipfile
from src.aws_clients import s3_client, dynamodb_client

# env defaults (safe if CI already exports)
os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4566")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("ARTIFACTS_BUCKET", "pkg-artifacts")
os.environ.setdefault("DDB_TABLE_PACKAGES", "packages")
os.environ.setdefault("DDB_TABLE_UPLOADS", "uploads")
os.environ.setdefault("DDB_TABLE_USERS", "users")
os.environ.setdefault("DDB_TABLE_TOKENS", "tokens")
os.environ.setdefault("DDB_TABLE_DOWNLOADS", "downloads")

def _wait_ddb_active(ddb, table):
    for _ in range(40):
        if ddb.describe_table(TableName=table)["Table"]["TableStatus"] == "ACTIVE":
            return
        time.sleep(0.5)
    raise RuntimeError(f"DDB table {table} not ACTIVE in time")

def setup_localstack_resources(seed_artifact=True):
    s3 = s3_client()
    ddb = dynamodb_client()

    bucket = os.environ["ARTIFACTS_BUCKET"]
    tables = {
        os.environ["DDB_TABLE_USERS"]:   {"hash": ("user_id","S")},
        os.environ["DDB_TABLE_TOKENS"]:  {"hash": ("token_id","S"), "ttl": "exp_ts"},
        os.environ["DDB_TABLE_PACKAGES"]:{ "hash": ("pkg_key","S")},
        os.environ["DDB_TABLE_UPLOADS"]: { "hash": ("upload_id","S")},
        os.environ["DDB_TABLE_DOWNLOADS"]:{
            "hash": ("event_id","S"),
            "gsi": {
                "name": "user-timestamp-index",
                "hash": ("user_id","S"),
                "range":("timestamp","S")
            }
        }
    }

    # S3 bucket
    existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    if bucket not in existing:
        s3.create_bucket(Bucket=bucket)

    # DDB tables
    existing = set(ddb.list_tables().get("TableNames", []))
    for name, spec in tables.items():
        if name in existing:
            continue
        attr_defs = [{"AttributeName": spec["hash"][0], "AttributeType": spec["hash"][1]}]
        key_schema = [{"AttributeName": spec["hash"][0], "KeyType": "HASH"}]
        gsi = []
        if "gsi" in spec:
            gh, gt = spec["gsi"]["hash"]
            rr, rt = spec["gsi"]["range"]
            attr_defs += [{"AttributeName": gh, "AttributeType": gt},
                          {"AttributeName": rr, "AttributeType": rt}]
            gsi = [{
                "IndexName": spec["gsi"]["name"],
                "KeySchema": [
                    {"AttributeName": gh, "KeyType": "HASH"},
                    {"AttributeName": rr, "KeyType": "RANGE"}
                ],
                "Projection": {"ProjectionType": "ALL"}
            }]
        ddb.create_table(
            TableName=name,
            AttributeDefinitions=attr_defs,
            KeySchema=key_schema,
            BillingMode="PAY_PER_REQUEST",
            GlobalSecondaryIndexes=gsi or None
        )
        _wait_ddb_active(ddb, name)

    # Seed a tiny model.zip if the rating flow expects it
    if seed_artifact:
        # demo/1.0.0/model.zip → in-memory zip with a README
        key = "models/demo/1.0.0/model.zip"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("README.txt", "demo model")
        buf.seek(0)
        s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue(), ContentType="application/zip")
