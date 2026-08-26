#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,subprocess,sys,urllib.request
from pathlib import Path
REPOSITORY="Anurag9000/Gram-Connect";COMMIT="294af1b35689a2eefb9453a96eec3ed9c66b68ec";SHA="6043605115ddf934433380e892f1f238eb9e4af236c4063350f477bc5cb0d4dc";URL=f"https://raw.githubusercontent.com/Anurag9000/RigorousRAG/{COMMIT}/tools/universal_training_controller.py";ROOT=Path(__file__).resolve().parent
PROFILE={"repository":REPOSITORY,"preferred_training_entrypoints":["train.py","training.py","run_training.py","scripts/train.py","scripts/train_all.py","scripts/run_training.py"],"preferred_dataset_entrypoints":["prepare_data.py","scripts/prepare_data.py","scripts/download_data.py","scripts/materialize_datasets.py","scripts/dataset_setup.py"],"dynamic_registry_covers":[],"extra_jobs":[],"ignore_entrypoints":["run_all_training.py"]}
def h(b):return hashlib.sha256(b).hexdigest()
def main():
 c=ROOT/".training_control"/"universal_training_controller.py";l=ROOT/"tools"/"universal_training_controller.py";p=l if l.is_file() and h(l.read_bytes())==SHA else c
 if not p.is_file() or h(p.read_bytes())!=SHA:
  c.parent.mkdir(parents=True,exist_ok=True);d=urllib.request.urlopen(URL,timeout=60).read()
  if h(d)!=SHA:raise RuntimeError("Pinned training controller checksum mismatch")
  t=c.with_suffix(".tmp");t.write_bytes(d);os.replace(t,c);p=c
 e=os.environ.copy();e["TRAINING_CONTROL_PROFILE"]=json.dumps(PROFILE,separators=(",",":"));e["TRAINING_CONTROL_REPO_ROOT"]=str(ROOT);return subprocess.call([sys.executable,str(p),*sys.argv[1:]],cwd=ROOT,env=e)
if __name__=="__main__":raise SystemExit(main())
