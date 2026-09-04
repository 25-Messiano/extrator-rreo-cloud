from __future__ import annotations

import io
import zipfile

import core.download_lote as dl


class FakeBlob:
    def __init__(self, name: str, payload: bytes = b"PDF"):
        self.name = name
        self.payload = payload
        self.uploaded = b""

    def download_to_file(self, fh, timeout=None):
        fh.write(self.payload)

    def upload_from_filename(self, filename, content_type=None, timeout=None):
        with open(filename, "rb") as f:
            self.uploaded = f.read()

    def generate_signed_url(self, **kwargs):
        return f"https://example.invalid/{self.name}"


class FakeBucket:
    def __init__(self):
        self.blobs = {}

    def blob(self, name):
        return self.blobs.setdefault(name, FakeBlob(name))


class FakeClient:
    def __init__(self):
        self.buckets = {}

    def bucket(self, name):
        return self.buckets.setdefault(name, FakeBucket())


def test_normalize_bimestre():
    assert dl.normalize_bimestre("B6") == "B6"
    assert dl.normalize_bimestre(2) == "B2"
    assert dl.normalize_bimestre("99") == "B6"


def test_prepare_state_zip_streams_and_uploads(monkeypatch):
    client = FakeClient()
    source_bucket = client.bucket(dl.RREO_SOURCE_BUCKET)
    source_bucket.blobs["base/a.pdf"] = FakeBlob("base/a.pdf", b"AAA")
    source_bucket.blobs["base/b.pdf"] = FakeBlob("base/b.pdf", b"BBB")

    monkeypatch.setattr(dl, "get_storage_client", lambda: client)
    monkeypatch.setattr(dl, "_collect_state_files", lambda uf, year, bim: [
        {"name": "a.pdf", "blob_name": "base/a.pdf", "size": 3},
        {"name": "b.pdf", "blob_name": "base/b.pdf", "size": 3},
    ])

    pkg = dl.prepare_rreo_zip("ESTADO", 2025, 6, "AC")
    assert pkg.pdf_count == 2
    assert pkg.filename == "RREO_AC_2025_B6.zip"

    uploaded = client.bucket(dl.BUCKET_NAME).blob(pkg.blob_name).uploaded
    with zipfile.ZipFile(io.BytesIO(uploaded)) as zf:
        assert sorted(zf.namelist()) == ["a.pdf", "b.pdf"]
        assert zf.read("a.pdf") == b"AAA"


def test_prepare_brazil_keeps_state_directories(monkeypatch):
    client = FakeClient()
    source = client.bucket(dl.RREO_SOURCE_BUCKET)
    source.blobs["ac/a.pdf"] = FakeBlob("ac/a.pdf", b"A")
    source.blobs["ba/b.pdf"] = FakeBlob("ba/b.pdf", b"B")

    monkeypatch.setattr(dl, "get_storage_client", lambda: client)
    monkeypatch.setattr(dl, "available_rreo_ufs", lambda year: ["AC", "BA"])

    def collect(uf, year, bim):
        if uf == "AC":
            return [{"name": "a.pdf", "blob_name": "ac/a.pdf", "size": 1}]
        return [{"name": "b.pdf", "blob_name": "ba/b.pdf", "size": 1}]

    monkeypatch.setattr(dl, "_collect_state_files", collect)
    pkg = dl.prepare_rreo_zip("BRASIL", 2025, 6)
    uploaded = client.bucket(dl.BUCKET_NAME).blob(pkg.blob_name).uploaded
    with zipfile.ZipFile(io.BytesIO(uploaded)) as zf:
        assert sorted(zf.namelist()) == ["AC/a.pdf", "BA/b.pdf"]


def test_signed_url_uses_results_bucket(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(dl, "get_storage_client", lambda: client)
    url = dl.signed_download_url("folder/test.zip")
    assert url.endswith("folder/test.zip")


def test_state_source_from_round_name():
    assert dl._state_source_from_round_name("RREO_AC_2025_B6_RODADA_NOVA_20260901_010101.xlsx") == ("AC", "RREO")
    assert dl._state_source_from_round_name("FNDE_BA_2025_RODADA_NOVA_20260901_010101.xlsx") == ("BA", "FNDE")
    assert dl._state_source_from_round_name("RREO_FNDE_MG_2025_B6_RODADA_NOVA_20260901_010101.xlsx") == ("MG", "RREO+FNDE")
    assert dl._state_source_from_round_name("RREO_FNDE_BRASIL_MASTER_2025.xlsx") == (None, None)


def test_latest_processed_state_spreadsheets(monkeypatch):
    from datetime import datetime, timezone
    old=datetime(2026,9,1,tzinfo=timezone.utc); new=datetime(2026,9,2,tzinfo=timezone.utc)
    monkeypatch.setattr(dl, "list_processed_rounds", lambda year: [
        {"uf":"AC","source":"RREO","name":"old.xlsx","blob_name":"r/old.xlsx","size":1,"updated":old},
        {"uf":"AC","source":"RREO","name":"new.xlsx","blob_name":"r/new.xlsx","size":2,"updated":new},
        {"uf":"BA","source":"RREO","name":"ba.xlsx","blob_name":"r/ba.xlsx","size":3,"updated":old},
    ])
    got=dl.latest_processed_state_spreadsheets(2025)
    assert [x["name"] for x in got] == ["new.xlsx","ba.xlsx"]


def test_inventory_processed_state_filters_uf(monkeypatch):
    monkeypatch.setattr(dl, "latest_processed_state_spreadsheets", lambda year: [
        {"uf":"AC","source":"RREO","name":"ac.xlsx","blob_name":"r/ac.xlsx","size":10,"updated":None},
        {"uf":"BA","source":"RREO","name":"ba.xlsx","blob_name":"r/ba.xlsx","size":20,"updated":None},
    ])
    inv=dl.inventory_processed_spreadsheets(2025,"ESTADO","AC","MAIS_RECENTES")
    assert inv["xlsx_count"] == 1
    assert inv["files"][0]["name"] == "ac.xlsx"


def test_prepare_processed_spreadsheets_zip(monkeypatch):
    client=FakeClient()
    source=client.bucket(dl.BUCKET_NAME)
    source.blobs["round/ac.xlsx"]=FakeBlob("round/ac.xlsx",b"ACX")
    source.blobs["round/ba.xlsx"]=FakeBlob("round/ba.xlsx",b"BAX")
    monkeypatch.setattr(dl,"get_storage_client",lambda:client)
    monkeypatch.setattr(dl,"inventory_processed_spreadsheets",lambda *args,**kwargs:{
        "scope":"BRASIL","uf":None,"year":2025,"selection":"MAIS_RECENTES","source_bytes":6,
        "files":[
            {"uf":"AC","name":"ac.xlsx","blob_name":"round/ac.xlsx","size":3},
            {"uf":"BA","name":"ba.xlsx","blob_name":"round/ba.xlsx","size":3},
        ]})
    pkg=dl.prepare_processed_spreadsheets_zip(2025,"BRASIL",None,"MAIS_RECENTES")
    uploaded=client.bucket(dl.BUCKET_NAME).blob(pkg.blob_name).uploaded
    with zipfile.ZipFile(io.BytesIO(uploaded)) as zf:
        assert sorted(zf.namelist()) == ["AC/ac.xlsx","BA/ba.xlsx"]
        assert zf.read("AC/ac.xlsx") == b"ACX"
