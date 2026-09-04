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
