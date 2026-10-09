from dotenv import load_dotenv; load_dotenv()
import os
import oci

cfg = oci.config.from_file()
cfg["pass_phrase"] = os.getenv("OCI_PASS_PHRASE")
oci.config.validate_config(cfg)

c = oci.object_storage.ObjectStorageClient(cfg)
ns = c.get_namespace().data
print("namespace:", ns)
print([b.name for b in c.list_buckets(ns, cfg["tenancy"]).data])
