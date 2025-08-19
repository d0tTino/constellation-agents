from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import agents.file_transfer as ft


class _Handler(BaseHTTPRequestHandler):
    """Simple handler that stores uploads and serves the stored file."""

    store: Path | None = None

    def do_PUT(self) -> None:  # noqa: N802 - HTTP verb
        assert self.store is not None
        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length)
        self.store.write_bytes(data)
        self.send_response(200)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - HTTP verb
        assert self.store is not None
        data = self.store.read_bytes()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:  # pragma: no cover - quiet
        return


def test_upload_and_download(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    src.write_text("hello world")
    dest = tmp_path / "dest.txt"
    _Handler.store = dest

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://{server.server_address[0]}:{server.server_port}"
    try:
        with patch("agents.file_transfer.check_permission", return_value=True) as cp:
            assert ft.upload_file(url, src, user_id="u1", group_id="g1")
            cp.assert_called_once_with("u1", "file:write", "g1")
        out = tmp_path / "out.txt"
        with patch("agents.file_transfer.check_permission", return_value=True) as cp:
            assert ft.download_file(url, out, user_id="u1", group_id="g1")
            cp.assert_called_once_with("u1", "file:read", "g1")
        assert out.read_text() == "hello world"
    finally:
        server.shutdown()
        thread.join()


def test_permission_denied(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    src.write_text("data")
    with patch("agents.file_transfer.check_permission", return_value=False) as cp, \
         patch("agents.file_transfer.requests.put") as mock_put:
        assert ft.upload_file("http://example.com", src, user_id="u1") is False
    cp.assert_called_once_with("u1", "file:write", None)
    mock_put.assert_not_called()

    dest = tmp_path / "dest.txt"
    with patch("agents.file_transfer.check_permission", return_value=False) as cp, \
         patch("agents.file_transfer.requests.get") as mock_get:
        assert ft.download_file("http://example.com", dest, user_id="u1") is False
    cp.assert_called_once_with("u1", "file:read", None)
    mock_get.assert_not_called()
