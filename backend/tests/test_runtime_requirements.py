"""Runtime file checks: no optional ASR imports, DLL loads, or GPU calls."""

import builtins
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

from streamlingo import runtime_requirements as requirements


@pytest.fixture(autouse=True)
def windows_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(requirements.sys, "platform", "win32")
    monkeypatch.setattr(requirements, "distribution", lambda name: SimpleNamespace(locate_file=lambda _: tmp_path / "wheel"))
    monkeypatch.setattr(requirements, "_visible_cuda_device_count", lambda: 1)


def runtime_files(directory, *, omit=()):
    directory.mkdir(parents=True, exist_ok=True)
    for name in requirements.WINDOWS_CUDA_DLLS:
        if name not in omit:
            (directory / name).touch()


def test_complete_runtime_leaves_entire_environment_unchanged(monkeypatch, caplog):
    monkeypatch.setattr(requirements, "missing_windows_cuda_dlls", lambda: ())
    before = dict(os.environ)
    with caplog.at_level("INFO"):
        requirements.require_windows_asr_runtime()
    assert dict(os.environ) == before
    assert "visible_cuda_devices=1" in caplog.text
    assert "still require model initialization" in caplog.text


@pytest.mark.parametrize("missing", requirements.WINDOWS_CUDA_DLLS)
def test_missing_component_fails_with_actionable_requirements_and_no_side_effects(monkeypatch, missing):
    monkeypatch.setattr(requirements, "missing_windows_cuda_dlls", lambda: (missing,))
    before = dict(os.environ)
    with pytest.raises(requirements.RuntimeRequirementsError) as raised:
        requirements.require_windows_asr_runtime()
    message = str(raised.value)
    assert missing in message
    assert "cuBLAS for CUDA 12" in message and "cuDNN 9" in message and "PATH" in message
    assert "Startup stopped" in message
    assert dict(os.environ) == before


def test_reports_all_missing_components(monkeypatch):
    missing = ("cublas64_12.dll", "cudnn_ops64_9.dll")
    monkeypatch.setattr(requirements, "missing_windows_cuda_dlls", lambda: missing)
    with pytest.raises(requirements.RuntimeRequirementsError) as raised:
        requirements.require_windows_asr_runtime()
    assert all(name in str(raised.value) for name in missing)


def test_non_windows_does_not_probe_or_change_environment(monkeypatch):
    monkeypatch.setattr(requirements.sys, "platform", "linux")
    monkeypatch.setattr(requirements, "missing_windows_cuda_dlls", lambda: pytest.fail("Windows-only check"))
    before = dict(os.environ)
    requirements.require_windows_asr_runtime()
    assert dict(os.environ) == before


def test_wheel_dispatcher_does_not_stand_in_for_full_cudnn_runtime(tmp_path, monkeypatch):
    wheel = tmp_path / "ctranslate2"
    wheel.mkdir()
    (wheel / "cudnn64_9.dll").touch()
    monkeypatch.setattr(requirements, "_windows_dll_directories", lambda: (wheel,))
    missing = requirements.missing_windows_cuda_dlls()
    assert "cudnn64_9.dll" not in missing
    assert "cudnn_ops64_9.dll" in missing and "cublas64_12.dll" in missing


def test_runtime_files_can_be_split_between_wheel_and_path(tmp_path, monkeypatch):
    wheel, external = tmp_path / "wheel", tmp_path / "cuda"
    wheel.mkdir()
    (wheel / "cudnn64_9.dll").touch()
    runtime_files(external, omit=("cudnn64_9.dll",))
    monkeypatch.setattr(requirements, "_windows_dll_directories", lambda: (wheel, external))
    assert requirements.missing_windows_cuda_dlls() == ()
    (external / "cublas64_12.dll").unlink()
    (external / "cublas64_12.dll").mkdir()
    assert requirements.missing_windows_cuda_dlls() == ("cublas64_12.dll",)


def test_lookup_includes_loader_locations_but_not_cuda_path_alone(tmp_path, monkeypatch):
    wheel, python, system, external = (tmp_path / name for name in ("wheel", "python", "windows", "cuda"))
    unused = tmp_path / "unsearched-cuda"
    runtime_files(unused / "bin")
    monkeypatch.setattr(requirements, "distribution", lambda name: SimpleNamespace(locate_file=lambda _: wheel))
    monkeypatch.setattr(requirements.sys, "executable", str(python / "python.exe"))
    monkeypatch.setenv("SystemRoot", str(system))
    monkeypatch.setenv("PATH", f';"{external}";;')
    monkeypatch.setenv("CUDA_PATH", str(unused))
    assert requirements._windows_dll_directories() == (wheel, python, system / "System32", system, external)
    assert requirements.missing_windows_cuda_dlls() == requirements.WINDOWS_CUDA_DLLS


def test_uninstalled_optional_package_does_not_break_file_scan(monkeypatch):
    def missing_distribution(_):
        raise requirements.PackageNotFoundError("ctranslate2")
    monkeypatch.setattr(requirements, "distribution", missing_distribution)
    assert Path(sys.executable).parent in requirements._windows_dll_directories()


def test_cli_stops_before_app_import_when_requirements_are_missing(monkeypatch, capsys):
    from streamlingo import cli

    monkeypatch.setattr(sys, "argv", ["streamlingo-server"])
    monkeypatch.setattr(requirements, "missing_windows_cuda_dlls", lambda: ("cublas64_12.dll",))
    monkeypatch.setattr(requirements, "_visible_cuda_device_count", lambda: pytest.fail("DLL check must run before GPU query"))
    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        if name == "streamlingo.app" or name.split(".")[0] in ("torch", "ctranslate2", "faster_whisper", "whisperlivekit"):
            pytest.fail(f"Runtime failure must occur before importing {name}")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(cli.uvicorn, "run", lambda *args, **kwargs: pytest.fail("Server must not start"))
    before = dict(os.environ)
    with pytest.raises(SystemExit) as raised:
        cli.main()
    assert raised.value.code == 2
    assert "cublas64_12.dll" in capsys.readouterr().err
    assert dict(os.environ) == before


def test_cli_preserves_normal_app_path_when_runtime_is_complete(monkeypatch):
    from streamlingo import cli

    monkeypatch.setattr(sys, "argv", ["streamlingo-server"])
    monkeypatch.setattr(requirements, "missing_windows_cuda_dlls", lambda: ())
    fake_app = ModuleType("streamlingo.app")
    sentinel = object()
    fake_app.create_app = lambda _: sentinel
    monkeypatch.setitem(sys.modules, "streamlingo.app", fake_app)
    runs = []
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, **kwargs: runs.append((app, kwargs)))
    before = dict(os.environ)
    cli.main()
    assert runs[0][0] is sentinel and runs[0][1]["workers"] == 1
    assert dict(os.environ) == before


def test_demo_cli_skips_runtime_requirements(monkeypatch):
    from streamlingo import cli

    monkeypatch.setattr(sys, "argv", ["streamlingo-server", "--mode", "demo"])
    monkeypatch.setattr(cli, "require_windows_asr_runtime", lambda: pytest.fail("Demo needs no ASR runtime"))
    fake_app = ModuleType("streamlingo.app")
    fake_app.create_app = lambda _: object()
    monkeypatch.setitem(sys.modules, "streamlingo.app", fake_app)
    monkeypatch.setattr(cli.uvicorn, "run", lambda *args, **kwargs: None)
    before = dict(os.environ)
    cli.main()
    assert dict(os.environ) == before


def test_cli_rejects_removed_device_override(monkeypatch, capsys):
    from streamlingo import cli

    monkeypatch.setattr(sys, "argv", ["streamlingo-server", "--asr-device", "cpu"])
    with pytest.raises(SystemExit) as raised:
        cli.main()
    assert raised.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_missing_asr_dependency_has_a_clear_setup_error(monkeypatch):
    def missing_distribution(_):
        raise requirements.PackageNotFoundError("ctranslate2")
    monkeypatch.setattr(requirements, "distribution", missing_distribution)
    monkeypatch.setattr(requirements, "_visible_cuda_device_count", lambda: pytest.fail("No dependency means no GPU query"))
    with pytest.raises(requirements.RuntimeRequirementsError, match="dependency is missing.*Setup-StreamLingo"):
        requirements.require_windows_asr_runtime()


def test_no_visible_gpu_stops_without_changing_environment(monkeypatch):
    monkeypatch.setattr(requirements, "missing_windows_cuda_dlls", lambda: ())
    monkeypatch.setattr(requirements, "_visible_cuda_device_count", lambda: 0)
    before = dict(os.environ)
    with pytest.raises(requirements.RuntimeRequirementsError, match="No usable CUDA device.*CPU fallback is not enabled"):
        requirements.require_windows_asr_runtime()
    assert dict(os.environ) == before


@pytest.mark.parametrize("error, expected", [
    (ModuleNotFoundError("No module named ctranslate2"), "dependency could not be imported"),
    (OSError("native library could not be loaded"), "could not check CUDA devices"),
    (RuntimeError("driver unavailable"), "could not check CUDA devices"),
])
def test_native_device_check_failure_has_actionable_error(monkeypatch, error, expected):
    monkeypatch.setattr(requirements, "missing_windows_cuda_dlls", lambda: ())
    def fail_query():
        raise error
    monkeypatch.setattr(requirements, "_visible_cuda_device_count", fail_query)
    with pytest.raises(requirements.RuntimeRequirementsError) as raised:
        requirements.require_windows_asr_runtime()
    assert expected in str(raised.value)
    assert "docs/runtime-requirements.md" in str(raised.value)


@pytest.mark.parametrize("platform, missing, expected_status, expected_exit", [
    ("win32", (), "ok", 0),
    ("win32", ("cublas64_12.dll",), "missing", 2),
    ("linux", (), "not_applicable", 0),
])
def test_doctor_entry_point_is_file_only(monkeypatch, capsys, platform, missing, expected_status, expected_exit):
    monkeypatch.setattr(requirements.sys, "platform", platform)
    monkeypatch.setattr(requirements, "missing_windows_cuda_dlls", lambda: missing)
    monkeypatch.setattr(requirements, "_visible_cuda_device_count", lambda: pytest.fail("Doctor must not query GPUs"))
    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in ("torch", "ctranslate2", "faster_whisper", "whisperlivekit"):
            pytest.fail(f"Doctor must not import {name}")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    before = dict(os.environ)
    assert requirements.main() == expected_exit
    report = json.loads(capsys.readouterr().out)
    assert report["platform"] == platform and report["status"] == expected_status
    assert report["missing_dlls"] == list(missing)
    assert dict(os.environ) == before
