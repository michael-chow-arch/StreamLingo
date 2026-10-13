"""Windows runtime requirements checked before starting the ASR model.

The pinned faster-whisper/CTranslate2 stack needs CUDA 12 cuBLAS and cuDNN 9.
The diagnostic module entry point checks files only. Service startup additionally
checks CTranslate2's visible CUDA device count. Neither path changes the device
selection/environment or loads an ASR model.
"""

from importlib.metadata import PackageNotFoundError, distribution
import json
import logging
import os
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

# CTranslate2 4.8.3 Windows wheel: CUDA 12 and cuDNN 9. Its bundled
# cudnn64_9.dll is a dispatcher, not the complete cuDNN runtime.
# https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/README.md#gpu
WINDOWS_CUDA_DLLS = (
    "cublas64_12.dll",
    "cublasLt64_12.dll",
    "cudnn64_9.dll",
    "cudnn_ops64_9.dll",
    "cudnn_cnn64_9.dll",
    "cudnn_adv64_9.dll",
    "cudnn_graph64_9.dll",
    "cudnn_heuristic64_9.dll",
    "cudnn_engines_precompiled64_9.dll",
    "cudnn_engines_runtime_compiled64_9.dll",
)


class RuntimeRequirementsError(RuntimeError):
    """The local Windows ASR runtime cannot meet the startup requirements."""


def _windows_dll_directories() -> tuple[Path, ...]:
    """Inspect known loader locations without importing native packages.

    CTranslate2 explicitly loads DLLs shipped in its package. External CUDA
    libraries are normally made available through PATH. Do not count arbitrary
    installed packages or CUDA_PATH alone: their files are not necessarily in
    the search path for cuDNN's dependencies. Inference compatibility remains a
    separate model initialization check.
    """
    paths: list[Path] = []
    try:
        paths.append(Path(distribution("ctranslate2").locate_file("ctranslate2")))
    except PackageNotFoundError:
        pass  # The normal ASR initialization reports a missing optional package.
    paths.append(Path(sys.executable).parent)
    windows_dir = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if windows_dir:
        paths.extend((Path(windows_dir) / "System32", Path(windows_dir)))
    for entry in os.environ.get("PATH", "").split(";"):
        entry = entry.strip().strip('"')
        if entry:
            paths.append(Path(entry))
    return tuple(dict.fromkeys(paths))


def missing_windows_cuda_dlls() -> tuple[str, ...]:
    """Return absent runtime filenames; never load a DLL or query the GPU."""
    directories = _windows_dll_directories()
    return tuple(name for name in WINDOWS_CUDA_DLLS
                 if not any((directory / name).is_file() for directory in directories))


def _missing_dll_message(missing: tuple[str, ...]) -> str:
    return (
        "Windows speech recognition requirements are not met. Missing runtime DLLs: "
        + ", ".join(missing)
        + ". Install cuBLAS for CUDA 12 and the complete cuDNN 9 runtime for CUDA 12, "
        "make their DLL directories available in PATH, then open a new launcher window. "
        "A compatible NVIDIA GPU/driver is also required; a working Ollama installation "
        "does not supply these libraries to this Python service. "
        "See docs/runtime-requirements.md. Startup stopped; no device or environment changes were made."
    )


def _visible_cuda_device_count() -> int:
    # Lazy import is intentional: the Doctor/file-only path must never load CT2.
    from ctranslate2 import get_cuda_device_count

    return get_cuda_device_count()


def require_windows_asr_runtime() -> None:
    """Require Windows runtime files and a CUDA device before starting ASR.

    Only normal Windows service startup imports CTranslate2 for its device-count
    query. No ASR model is constructed and the environment is never changed.
    Non-Windows startup is unchanged. Model initialization still checks library
    compatibility and memory availability; device presence does not prove speed.
    """
    if sys.platform != "win32":
        return
    try:
        distribution("ctranslate2")
    except PackageNotFoundError as exc:
        raise RuntimeRequirementsError(
            "The CTranslate2 speech recognition dependency is missing. "
            "Run Setup-StreamLingo.cmd to install the backend ASR dependencies. "
            "See docs/runtime-requirements.md. Startup stopped."
        ) from exc
    missing = missing_windows_cuda_dlls()
    if missing:
        raise RuntimeRequirementsError(_missing_dll_message(missing))
    try:
        device_count = _visible_cuda_device_count()
    except ImportError as exc:
        raise RuntimeRequirementsError(
            "The CTranslate2 speech recognition dependency could not be imported. "
            "Run Setup-StreamLingo.cmd and verify the Windows native runtime requirements. "
            f"Details: {exc}. See docs/runtime-requirements.md. Startup stopped."
        ) from exc
    except Exception as exc:
        raise RuntimeRequirementsError(
            "CTranslate2 could not check CUDA devices. Verify the NVIDIA driver and "
            f"CUDA 12/cuDNN 9 runtime installation. Details: {exc}. "
            "See docs/runtime-requirements.md. Startup stopped."
        ) from exc
    if device_count <= 0:
        raise RuntimeRequirementsError(
            "No usable CUDA device is visible to CTranslate2. Windows speech recognition "
            "requires a compatible NVIDIA GPU and driver; check that the GPU is available "
            "to this process. CPU fallback is not enabled. "
            "See docs/runtime-requirements.md. Startup stopped."
        )
    logger.info(
        "ASR_RUNTIME Windows CUDA 12/cuDNN 9 runtime files found; visible_cuda_devices=%s. "
        "Library compatibility and memory availability still require model initialization/inference.",
        device_count,
    )


def main() -> int:
    """Doctor entry point: report DLL files only, without importing CTranslate2."""
    missing = missing_windows_cuda_dlls() if sys.platform == "win32" else ()
    status = "missing" if missing else "ok" if sys.platform == "win32" else "not_applicable"
    message = (_missing_dll_message(missing) if missing else
               "DLL file check only; CUDA device availability and inference compatibility were not tested."
               if sys.platform == "win32" else "Windows DLL file check does not apply to this platform.")
    print(json.dumps({"platform": sys.platform, "status": status,
                      "missing_dlls": missing, "message": message}))
    return 2 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
