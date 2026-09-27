"""Blob-verified loader for transactional dataset-cohort runtime v3."""
from __future__ import annotations
import hashlib,importlib.util,os,sys,urllib.request
from pathlib import Path
R='Anurag9000/RigorousRAG';C1='955a092e4a3e2cc04adfd8007206acd6d1341dce';P1='training/dataset_cohort_runtime.py';B1='8afef6ade42b9885878102d42e26ec3ab2a18bf3';C2='0160deb303f6a4d2a48b8453244dc01ceaae1295';P2='training/dataset_cohort_runtime_v3.py';B2='e6455266b63bed08691cfa76e620060f99eca35a';RUNTIME_REPOSITORY=R;RUNTIME_COMMIT=C2;RUNTIME_PATH=P2;RUNTIME_BLOB=B2
def H(d):return hashlib.sha1(f'blob {len(d)}\0'.encode()+d).hexdigest()
def G(r,c,p,b):
 t=r/'.training_control'/'dataset_cohort'/c/Path(p).name
 if t.is_file() and H(t.read_bytes())==b:return t
 d=urllib.request.urlopen(urllib.request.Request(f'https://raw.githubusercontent.com/{R}/{c}/{p}',headers={'User-Agent':'opf-dataset-cohort-v3'}),timeout=120).read()
 if H(d)!=b:raise RuntimeError('cohort runtime checksum mismatch')
 t.parent.mkdir(parents=True,exist_ok=True);q=t.with_suffix(t.suffix+'.tmp');q.write_bytes(d);os.replace(q,t);return t
def I(n,p):
 if n in sys.modules:return sys.modules[n]
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
def materialize_runtime(root=None):
 r=(root or Path(os.environ.get('TRAINING_CONTROL_REPO_ROOT') or '.')).resolve();G(r,C1,P1,B1);return G(r,C2,P2,B2)
def load_runtime(root=None):
 r=(root or Path(os.environ.get('TRAINING_CONTROL_REPO_ROOT') or '.')).resolve();I(f'_opf_dataset_cohort_runtime_{C1[:12]}',G(r,C1,P1,B1));m=I(f'_opf_dataset_cohort_runtime_v3_{C2[:12]}',G(r,C2,P2,B2));assert m.BASE_COMMIT==C1;return m
