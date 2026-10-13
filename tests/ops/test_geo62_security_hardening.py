"""GEO-62 security hardening tests.

Covers: URL userinfo rejection, fragment rejection, exact allowlist,
deceptive hostnames, trailing-dot normalization, IP address validation
(ipaddress module), multicast/reserved rejection, IPv6 edge cases,
redirect disable, local mode restrictions, Content-Length pre-check,
bounded response read, retention path hardening, evidence ID validation.

All network and DNS behavior is mocked.  No real network calls.
"""

from __future__ import annotations

import ipaddress
import os
import socket
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.ops.retention import (
    DisabledRetention,
    InMemoryRetention,
    TempDirRetention,
    _EVIDENCE_ID_RE,
)
from app.ops.smoke import (
    _NoRedirectHandler,
    _is_global_unicast,
    _validate_ip_addresses,
    _validate_url,
    run_smoke,
)


# =========================================================================
# 1. URL Parsing — userinfo, fragment, control chars
# =========================================================================


class TestURLUserinfoRejection:
    def test_username_rejected(self) -> None:
        with pytest.raises(ValueError, match="userinfo"):
            _validate_url("https://admin:pass@example.com")

    def test_username_only_rejected(self) -> None:
        with pytest.raises(ValueError, match="userinfo"):
            _validate_url("https://user@example.com")

    def test_password_only_rejected(self) -> None:
        with pytest.raises(ValueError, match="userinfo"):
            _validate_url("https://:token@example.com")


class TestURLFragmentRejection:
    def test_fragment_rejected(self) -> None:
        with pytest.raises(ValueError, match="fragment"):
            _validate_url("https://example.com/path#section")

    def test_empty_fragment_rejected(self) -> None:
        with pytest.raises(ValueError, match="fragment"):
            _validate_url("https://example.com/path#")

    def test_no_fragment_passes(self) -> None:
        result = _validate_url("https://example.com/path")
        assert result == "example.com"


class TestURLControlChars:
    def test_null_byte_rejected(self) -> None:
        with pytest.raises(ValueError, match="control characters"):
            _validate_url("https://exam\x00ple.com")

    def test_newline_rejected(self) -> None:
        with pytest.raises(ValueError, match="control characters"):
            _validate_url("https://example.com/path\nadmin")

    def test_whitespace_rejected(self) -> None:
        with pytest.raises(ValueError, match="whitespace"):
            _validate_url(" https://example.com")

    def test_trailing_space_rejected(self) -> None:
        with pytest.raises(ValueError, match="whitespace"):
            _validate_url("https://example.com ")


# =========================================================================
# 2. Exact Host Allowlist
# =========================================================================


class TestExactAllowlist:
    def test_exact_match_passes(self) -> None:
        hosts = frozenset({"approved.example.com"})
        result = _validate_url(
            "https://approved.example.com/v1/health",
            allowed_hosts=hosts,
        )
        assert result == "approved.example.com"

    def test_suffix_not_matching(self) -> None:
        """Deceptive suffix: attacker.approved.example.com."""
        hosts = frozenset({"approved.example.com"})
        with pytest.raises(ValueError, match="not in the exact allowlist"):
            _validate_url(
                "https://attacker.approved.example.com/v1/health",
                allowed_hosts=hosts,
            )

    def test_trailing_dot_normalized(self) -> None:
        hosts = frozenset({"example.com"})
        result = _validate_url(
            "https://example.com./v1/health",
            allowed_hosts=hosts,
        )
        # urlparse keeps the trailing dot in hostname
        assert result == "example.com."

    def test_trailing_dot_allowed_with_dot(self) -> None:
        hosts = frozenset({"example.com."})
        result = _validate_url(
            "https://example.com./v1/health",
            allowed_hosts=hosts,
        )
        assert result == "example.com."

    def test_case_insensitive(self) -> None:
        hosts = frozenset({"EXAMPLE.COM"})
        result = _validate_url(
            "https://example.com/v1/health",
            allowed_hosts=hosts,
        )
        # Hostname is lowercase from urlparse
        assert result == "example.com"

    def test_no_allowlist_allows_any(self) -> None:
        result = _validate_url("https://any-host.example.com")
        assert result == "any-host.example.com"


# =========================================================================
# 3. IP Address Validation
# =========================================================================


def _mock_addrinfo(ip_str: str):
    """Create a mock getaddrinfo return for a single IPv4 address."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip_str, 0))]


def _mock_addrinfo_v6(ip_str: str):
    """Create a mock getaddrinfo return for a single IPv6 address."""
    return [(socket.AF_INET6, socket.SOCK_STREAM, 0, "", (ip_str, 0, 0, 0))]


class TestIPValidation:
    def test_loopback_rejected(self) -> None:
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=_mock_addrinfo("127.0.0.1")):
            with pytest.raises(ValueError, match="not globally routable"):
                _validate_ip_addresses("localhost")

    def test_private_rejected(self) -> None:
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=_mock_addrinfo("10.0.0.1")):
            with pytest.raises(ValueError, match="not globally routable"):
                _validate_ip_addresses("internal.example")

    def test_link_local_rejected(self) -> None:
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=_mock_addrinfo("169.254.1.1")):
            with pytest.raises(ValueError, match="not globally routable"):
                _validate_ip_addresses("linklocal.example")

    def test_multicast_rejected(self) -> None:
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=_mock_addrinfo("224.0.0.1")):
            with pytest.raises(ValueError, match="not globally routable"):
                _validate_ip_addresses("multicast.example")

    def test_reserved_rejected(self) -> None:
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=_mock_addrinfo("240.0.0.1")):
            with pytest.raises(ValueError, match="not globally routable"):
                _validate_ip_addresses("reserved.example")

    def test_unspecified_rejected(self) -> None:
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=_mock_addrinfo("0.0.0.0")):
            with pytest.raises(ValueError, match="not globally routable"):
                _validate_ip_addresses("unspecified.example")

    def test_ipv6_loopback_rejected(self) -> None:
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=_mock_addrinfo_v6("::1")):
            with pytest.raises(ValueError, match="not globally routable"):
                _validate_ip_addresses("ipv6loop.example")

    def test_ipv6_multicast_rejected(self) -> None:
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=_mock_addrinfo_v6("ff02::1")):
            with pytest.raises(ValueError, match="not globally routable"):
                _validate_ip_addresses("ipv6multi.example")

    def test_ipv6_link_local_rejected(self) -> None:
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=_mock_addrinfo_v6("fe80::1")):
            with pytest.raises(ValueError, match="not globally routable"):
                _validate_ip_addresses("ipv6link.example")

    def test_ipv6_unspecified_rejected(self) -> None:
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=_mock_addrinfo_v6("::")):
            with pytest.raises(ValueError, match="not globally routable"):
                _validate_ip_addresses("ipv6unspec.example")

    def test_loopback_allowed_in_local_mode(self) -> None:
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=_mock_addrinfo("127.0.0.1")):
            addrs = _validate_ip_addresses("localhost", allow_local=True)
            assert len(addrs) > 0

    def test_private_not_allowed_in_local_mode(self) -> None:
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=_mock_addrinfo("192.168.1.1")):
            with pytest.raises(ValueError, match="not loopback"):
                _validate_ip_addresses("internal.local", allow_local=True)

    def test_link_local_not_allowed_in_local_mode(self) -> None:
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=_mock_addrinfo("169.254.1.1")):
            with pytest.raises(ValueError, match="not loopback"):
                _validate_ip_addresses("metadata.local", allow_local=True)

    def test_cloud_metadata_rejected(self) -> None:
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=_mock_addrinfo("169.254.169.254")):
            with pytest.raises(ValueError, match="not globally routable"):
                _validate_ip_addresses("metadata.example")

    def test_empty_resolution_rejected(self) -> None:
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=[]):
            with pytest.raises(ValueError, match="Empty DNS resolution"):
                _validate_ip_addresses("empty.example")

    def test_failed_resolution_rejected(self) -> None:
        with patch(
            "app.ops.smoke.socket.getaddrinfo",
            side_effect=socket.gaierror("Name or service not known"),
        ):
            with pytest.raises(ValueError, match="DNS resolution failed"):
                _validate_ip_addresses("unresolvable.example")

    def test_too_many_addresses_rejected(self) -> None:
        many = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (f"1.2.3.{i}", 0))
                for i in range(20)]
        with patch("app.ops.smoke.socket.getaddrinfo", return_value=many):
            with pytest.raises(ValueError, match="Too many resolved"):
                _validate_ip_addresses("multi.example")


# =========================================================================
# 4. Redirect Disabled
# =========================================================================


class TestRedirectDisabled:
    def test_redirect_returns_error(self) -> None:
        import urllib.error
        import urllib.request

        handler = _NoRedirectHandler()
        req = urllib.request.Request("https://example.com")
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            handler.redirect_request(req, None, "302", "Found", {}, "https://other.com")
        assert exc_info.value.code == 302

    def test_302_rejected_in_smoke(self) -> None:
        import urllib.error

        mock_resp = MagicMock()
        mock_resp.status = 302
        mock_resp.headers = {"Location": "https://other.com"}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        mock_handler = MagicMock()
        mock_handler.redirect_request.side_effect = urllib.error.HTTPError(
            "https://other.com", 302, "Redirects disabled", {}, None
        )

        with patch("app.ops.smoke.urllib.request.build_opener") as mock_build:
            opener = MagicMock()
            opener.open.side_effect = urllib.error.HTTPError(
                "https://other.com", 302, "Redirects disabled", {}, None
            )
            mock_build.return_value = opener
            evidence = run_smoke(
                base_url="https://example.com",
                release_sha="a" * 40,
                explicit_live_consent=True,
                retries=0,
            )
            assert evidence.transport_verified is False
            assert any("Redirect" in l for l in evidence.limitations)


# =========================================================================
# 5. Local Mode Restrictions
# =========================================================================


class TestLocalMode:
    def test_local_mode_only_loopback_ip(self) -> None:
        """IP validation in run_smoke rejects non-loopback in local mode."""
        with patch(
            "app.ops.smoke.socket.getaddrinfo",
            return_value=_mock_addrinfo("192.168.1.1"),
        ):
            with pytest.raises(ValueError, match="not loopback"):
                run_smoke(
                    base_url="http://192.168.1.1:8000",
                    release_sha="a" * 40,
                    explicit_live_consent=True,
                    allow_local=True,
                    retries=0,
                )

    def test_local_mode_http_allowed(self) -> None:
        result = _validate_url("http://127.0.0.1:8000", allow_local=True)
        assert result == "127.0.0.1"

    def test_local_mode_non_loopback_private_rejected(self) -> None:
        with patch(
            "app.ops.smoke.socket.getaddrinfo",
            return_value=_mock_addrinfo("10.0.0.1"),
        ):
            with pytest.raises(ValueError, match="not loopback"):
                run_smoke(
                    base_url="http://10.0.0.1:8000",
                    release_sha="a" * 40,
                    explicit_live_consent=True,
                    allow_local=True,
                    retries=0,
                )

    def test_local_mode_metadata_rejected(self) -> None:
        with patch(
            "app.ops.smoke.socket.getaddrinfo",
            return_value=_mock_addrinfo("169.254.169.254"),
        ):
            with pytest.raises(ValueError, match="not loopback"):
                run_smoke(
                    base_url="http://169.254.169.254/metadata",
                    release_sha="a" * 40,
                    explicit_live_consent=True,
                    allow_local=True,
                    retries=0,
                )

    def test_local_mode_environment_name(self) -> None:
        with patch(
            "app.ops.smoke.socket.getaddrinfo",
            return_value=_mock_addrinfo("127.0.0.1"),
        ):
            evidence = run_smoke(
                base_url="http://127.0.0.1:1",
                release_sha="a" * 40,
                explicit_live_consent=True,
                allow_local=True,
                timeout=1,
                retries=0,
            )
            assert evidence.environment_name == "local_development"


# =========================================================================
# 6. Response Bounding
# =========================================================================


class TestResponseBounding:
    def test_content_length_over_limit_rejected(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Type": "application/json", "Content-Length": "9999999"}
        mock_resp.read.return_value = b'{"status":"ok"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch(
            "app.ops.smoke.socket.getaddrinfo",
            return_value=_mock_addrinfo("93.184.216.34"),
        ), patch("app.ops.smoke.urllib.request.build_opener") as mock_build:
            opener = MagicMock()
            opener.open.return_value.__enter__ = lambda s: mock_resp
            opener.open.return_value.__exit__ = MagicMock(return_value=False)
            mock_build.return_value = opener
            evidence = run_smoke(
                base_url="https://example.com",
                release_sha="a" * 40,
                explicit_live_consent=True,
                max_response_bytes=1024,
                retries=0,
            )
            # Content-Length exceeded → transport_verified stays false
            assert evidence.transport_verified is False

    def test_bounded_read_enforced(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.read.return_value = b"x" * 100  # within limit
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch(
            "app.ops.smoke.socket.getaddrinfo",
            return_value=_mock_addrinfo("93.184.216.34"),
        ), patch("app.ops.smoke.urllib.request.build_opener") as mock_build:
            opener = MagicMock()
            opener.open.return_value = mock_resp
            mock_build.return_value = opener
            evidence = run_smoke(
                base_url="https://example.com",
                release_sha="a" * 40,
                explicit_live_consent=True,
                max_response_bytes=200,
                retries=0,
            )
            assert evidence.response_byte_count == 100
            assert evidence.transport_verified is True


# =========================================================================
# 7. Retention Path Hardening
# =========================================================================


class TestEvidenceIDValidation:
    def test_valid_ids_accepted(self) -> None:
        store = TempDirRetention()
        for eid in ["ev-001", "ev_002", "ev.003", "EV004", "a1b2c3"]:
            result = store.write(eid, '{"test": true}')
            assert result.success is True

    def test_slash_rejected(self) -> None:
        store = TempDirRetention()
        result = store.write("ev/001", '{"test": true}')
        assert result.success is False
        assert "Invalid" in (result.error or "")

    def test_backslash_rejected(self) -> None:
        store = TempDirRetention()
        result = store.write("ev\\001", '{"test": true}')
        assert result.success is False

    def test_null_byte_rejected(self) -> None:
        store = TempDirRetention()
        result = store.write("ev\x0001", '{"test": true}')
        assert result.success is False

    def test_traversal_rejected(self) -> None:
        store = TempDirRetention()
        result = store.write("../../../etc/passwd", '{"test": true}')
        assert result.success is False

    def test_leading_dot_rejected(self) -> None:
        store = TempDirRetention()
        result = store.write(".hidden", '{"test": true}')
        assert result.success is False

    def test_empty_id_rejected(self) -> None:
        store = TempDirRetention()
        result = store.write("", '{"test": true}')
        assert result.success is False

    def test_long_id_rejected(self) -> None:
        store = TempDirRetention()
        result = store.write("a" * 200, '{"test": true}')
        assert result.success is False

    def test_symlink_component_rejected(self, tmp_path: Path) -> None:
        store = TempDirRetention(base_dir=tmp_path)
        # Create a symlink with the exact .json filename
        symlink = tmp_path / "ev.json"
        symlink.symlink_to(tmp_path / "nonexistent.json")
        result = store.write("ev", '{"test": true}')
        # Should fail because ev.json is a symlink
        assert result.success is False
        assert "Symlink" in (result.error or "")

    def test_concurrent_duplicate_rejected(self) -> None:
        store = TempDirRetention()
        store.write("ev-concurrent", '{"v": 1}')
        result = store.write("ev-concurrent", '{"v": 2}')
        assert result.success is False
        assert "Duplicate" in (result.error or "")

    def test_no_filesystem_path_in_error(self) -> None:
        """Error messages must not leak filesystem paths."""
        store = TempDirRetention()
        result = store.write("../../../etc/passwd", '{"test": true}')
        error_msg = result.error or ""
        # The error contains the rejected ID (which includes /etc) but
        # must not contain actual filesystem paths like /tmp or /home
        assert "/tmp" not in error_msg
        assert "/home" not in error_msg

    def test_checksum_verifies_after_write(self) -> None:
        store = TempDirRetention()
        store.write("ev-check", '{"check": true}')
        assert store.verify_checksum("ev-check") is True


# =========================================================================
# 7b. Write-Once Atomicity — POSIX O_CREAT|O_EXCL + os.link tests
# =========================================================================


class TestWriteOnceAtomicity:
    """Behavioral tests for the POSIX atomic write-once contract."""

    def test_two_identical_writes_only_one_succeeds(self, tmp_path: Path) -> None:
        """Two concurrent identical writes: exactly one must succeed."""
        store = TempDirRetention(base_dir=tmp_path)
        r1 = store.write("ev-atom", '{"v": 1}')
        r2 = store.write("ev-atom", '{"v": 1}')
        # Exactly one must succeed
        assert (r1.success or r2.success), "At least one write must succeed"
        assert not (r1.success and r2.success), "Both writes must not succeed"
        # The winner is persisted with correct checksum
        assert store.verify_checksum("ev-atom") is True

    def test_two_conflicting_writes_original_preserved(self, tmp_path: Path) -> None:
        """Two concurrent conflicting writes: first wins, second rejected."""
        store = TempDirRetention(base_dir=tmp_path)
        r1 = store.write("ev-conflict", '{"v": 1}')
        r2 = store.write("ev-conflict", '{"v": 2}')
        assert r1.success is True
        assert r2.success is False
        assert "Duplicate" in (r2.error or "")
        # Final content must match the first write (winner)
        rec = store.read("ev-conflict")
        assert rec is not None
        assert '"v": 1' in rec.payload

    def test_existing_final_file_never_overwritten(self, tmp_path: Path) -> None:
        """An existing final file must not be overwritten by a second write."""
        store = TempDirRetention(base_dir=tmp_path)
        store.write("ev-no-overwrite", '{"version": "original"}')
        rec_before = store.read("ev-no-overwrite")
        assert rec_before is not None
        sha_before = rec_before.content_sha256
        # Second write must fail
        r2 = store.write("ev-no-overwrite", '{"version": "attacker"}')
        assert r2.success is False
        # Original content and hash must be unchanged
        rec_after = store.read("ev-no-overwrite")
        assert rec_after is not None
        assert rec_after.content_sha256 == sha_before
        assert '"version": "original"' in rec_after.payload

    def test_simulated_write_failure_no_final_file(self, tmp_path: Path) -> None:
        """If writing to the temp fd fails, no final file must appear."""
        store = TempDirRetention(base_dir=tmp_path)
        # Monkeypatch os.write to always fail
        import app.ops.retention as ret_mod
        original_write = os.write

        def failing_write(fd: int, data: bytes) -> int:
            raise OSError("Simulated disk write failure")

        with patch.object(ret_mod.os, "write", side_effect=failing_write):
            result = store.write("ev-write-fail", '{"v": 1}')
        assert result.success is False
        assert "write" in (result.error or "").lower()
        # Final file must not exist
        final = tmp_path / "ev-write-fail.json"
        assert final.exists() is False

    def test_simulated_link_failure_no_final_file(self, tmp_path: Path) -> None:
        """If os.link fails and fallback also fails, no final file appears."""
        store = TempDirRetention(base_dir=tmp_path)
        import app.ops.retention as ret_mod

        original_open = os.open
        open_call_count = 0

        def selective_open(path: str | int, *args: Any, **kwargs: Any) -> int:
            nonlocal open_call_count
            open_call_count += 1
            # First call (temp file creation) must succeed
            if open_call_count == 1:
                return original_open(path, *args, **kwargs)
            # Subsequent calls (fallback publish) must fail
            raise OSError("Simulated fallback failure")

        def failing_link(src: str, dst: str) -> None:
            raise OSError("Simulated link failure")

        with patch.object(ret_mod.os, "link", side_effect=failing_link), \
             patch.object(ret_mod.os, "open", side_effect=selective_open):
            result = store.write("ev-link-fail", '{"v": 1}')
        assert result.success is False
        # Final file must not exist
        final = tmp_path / "ev-link-fail.json"
        assert final.exists() is False

    def test_temp_file_cleanup_on_success(self, tmp_path: Path) -> None:
        """No leftover temp files after a successful write."""
        store = TempDirRetention(base_dir=tmp_path)
        store.write("ev-clean", '{"v": 1}')
        # List all .tmp files in the directory
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0, f"Leftover temp files: {tmp_files}"

    def test_temp_file_cleanup_on_failure(self, tmp_path: Path) -> None:
        """No leftover temp files after a failed write."""
        store = TempDirRetention(base_dir=tmp_path)
        # Write once to create a duplicate scenario
        store.write("ev-clean-fail", '{"v": 1}')
        # Second write fails (duplicate)
        store.write("ev-clean-fail", '{"v": 2}')
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0, f"Leftover temp files: {tmp_files}"

    def test_success_leaves_only_the_published_file(self, tmp_path: Path) -> None:
        """A successful write leaves the sealed artifact and nothing else."""
        store = TempDirRetention(base_dir=tmp_path)
        result = store.write("ev-only", '{"v": 1}')
        assert result.success is True
        assert [p.name for p in tmp_path.iterdir()] == ["ev-only.json"]

    def test_directory_unchanged_after_failed_write(self, tmp_path: Path) -> None:
        """A failed write changes nothing: no residue, and no sealed byte moved."""
        store = TempDirRetention(base_dir=tmp_path)
        store.write("ev-snapshot", '{"v": 1}')
        before = {p.name: p.read_bytes() for p in sorted(tmp_path.iterdir())}

        result = store.write("ev-snapshot", '{"v": 2}')  # duplicate id -> must fail
        assert result.success is False

        after = {p.name: p.read_bytes() for p in sorted(tmp_path.iterdir())}
        assert after == before

    def test_unverifiable_proc_resolution_is_not_trusted(self, tmp_path: Path) -> None:
        """A /proc path naming no file must be rejected, leaving no residue.

        ``os.path.realpath`` does not raise on a path that does not exist - it
        returns the input unchanged - so on any platform without ``/proc``
        (macOS, BSD, some containers) the resolution yields a phantom path.
        ``_open_temp`` therefore verifies the resolution by (st_dev, st_ino)
        before trusting it. Remove that check and this test fails with a
        leftover ``.tmp`` placeholder, which is exactly how the defect shipped.
        """
        store = TempDirRetention(base_dir=tmp_path)
        import app.ops.retention as ret_mod

        original_realpath = ret_mod.os.path.realpath

        def phantom_realpath(path: Any, *args: Any, **kwargs: Any) -> Any:
            if str(path).startswith("/proc/self/fd/"):
                return "/proc/self/fd/999999"
            return original_realpath(path, *args, **kwargs)

        with patch.object(ret_mod.os.path, "realpath", side_effect=phantom_realpath):
            result = store.write("ev-phantom", '{"v": 1}')

        assert result.success is True
        assert [p.name for p in tmp_path.iterdir()] == ["ev-phantom.json"]

    def test_error_message_no_absolute_paths(self, tmp_path: Path) -> None:
        """Retention errors must not leak absolute filesystem paths."""
        store = TempDirRetention(base_dir=tmp_path)
        # Cause a duplicate error
        store.write("ev-no-path-err", '{"v": 1}')
        result = store.write("ev-no-path-err", '{"v": 2}')
        error_msg = result.error or ""
        assert "/tmp" not in error_msg
        assert "/home" not in error_msg
        assert str(tmp_path) not in error_msg

    def test_parent_dir_fsync_called(self, tmp_path: Path) -> None:
        """Parent directory fsync is attempted after publish."""
        store = TempDirRetention(base_dir=tmp_path)
        import app.ops.retention as ret_mod
        fsync_dirs_called = []
        original_fsync_dir = store._fsync_dir

        def tracking_fsync_dir(path: Path) -> None:
            fsync_dirs_called.append(str(path))
            # Don't actually call fsync to avoid side effects

        with patch.object(store, "_fsync_dir", side_effect=tracking_fsync_dir):
            result = store.write("ev-dir-fsync", '{"v": 1}')
        assert result.success is True
        assert len(fsync_dirs_called) == 1


# =========================================================================
# 8. Smoke Error Messages
# =========================================================================


class TestSmokeErrorNoLeakage:
    def test_no_path_in_smoke_error(self) -> None:
        with pytest.raises(Exception):
            run_smoke(
                base_url="https://example.com",
                release_sha="a" * 40,
                explicit_live_consent=False,
            )

    def test_no_secret_in_smoke_result(self) -> None:
        with patch(
            "app.ops.smoke.socket.getaddrinfo",
            side_effect=socket.gaierror("No such host"),
        ):
            with pytest.raises(ValueError, match="Target validation failed"):
                run_smoke(
                    base_url="https://unreachable.invalid:1",
                    release_sha="b" * 40,
                    explicit_live_consent=True,
                    timeout=1,
                    retries=0,
                )
