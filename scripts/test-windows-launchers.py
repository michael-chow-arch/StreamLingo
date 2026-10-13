"""Exercise Windows launchers in copied fixtures; never install or start a service."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "launcher-review" / str(uuid4())
POWERSHELL = Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
RESULTS = []
ASSETS = ["background.js", "popup.html", "popup.js", "popup.css", "offscreen.html", "offscreen.js",
          "content.js", "pcm-worklet.js", "_locales/en/messages.json", "_locales/zh_CN/messages.json",
          *[f"icons/icon{size}.png" for size in (16, 32, 48, 128)]]


def put(path, text="fixture"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def fixture(name, *, source=False, config=None):
    directory = OUTPUT / (name + " spaced path")
    for script in ("setup", "start", "stop", "doctor"):
        destination = directory / "scripts" / f"{script}.ps1"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "scripts" / f"{script}.ps1", destination)
    put(directory / "package.json", '{"version":"0.2.0"}')
    put(directory / "dist" / "extension" / "manifest.json", '{"version":"0.2.0"}')
    for asset in ASSETS:
        put(directory / "dist" / "extension" / asset)
    if source:
        (directory / "extension" / "src").mkdir(parents=True)
    if config is not None:
        put(directory / ".streamlingo.json", config if isinstance(config, str) else json.dumps(config))
    return directory


def config(**changes):
    return dict(version=1, ollamaModel="chat:latest", ollamaUrl="http://127.0.0.1:11434",
                extensionId="a" * 32, asrModel="base", **changes)


def model_files(directory, omit=None):
    put(directory / "backend" / ".venv" / "Scripts" / "python.exe", "NOT AN EXECUTABLE")
    for name in ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt"):
        if name != omit:
            put(directory / "models" / "whisper-base" / name)


def run(name, directory, script, *, arguments="", mocks="", expected="", success=False, expected_exit=None):
    wrapper = directory / "verify.ps1"
    put(wrapper, r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
function Stop-Process { throw 'UNEXPECTED REAL STOP ATTEMPT' }
function Start-Process { throw 'UNEXPECTED REAL START ATTEMPT' }
function Invoke-RestMethod { throw 'UNEXPECTED NETWORK ATTEMPT' }
function Get-NetTCPConnection { return $null }
function Get-CimInstance { throw 'UNEXPECTED PROCESS ENUMERATION' }
function Get-Process { return $null }
function Get-Command { param($Name) throw 'FIXTURE_DEPENDENCY_BOUNDARY' }
""" + mocks + f"""
try {{ & {quote(directory / 'scripts' / (script + '.ps1'))} {arguments}; {"exit $LASTEXITCODE" if script == "doctor" else "Write-Output 'FIXTURE_SCRIPT_FINISHED'"} }}
catch {{ Write-Output ('FIXTURE_ERROR: ' + $_.Exception.Message); exit 23 }}
""")
    result = subprocess.run([str(POWERSHELL), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(wrapper)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    output = result.stdout + result.stderr
    ok = expected in output and result.returncode == (expected_exit if expected_exit is not None else 0 if success else 23)
    RESULTS.append(dict(name=name, passed=ok, exit_code=result.returncode, output=output))
    print(("PASS" if ok else "FAIL"), name)
    if not ok:
        print(output)
    return output


def ollama(models, *, unknown=False):
    payload = json.dumps([dict(name=name) for name in models])
    return f"""
function Invoke-RestMethod {{
    param($Uri, $Method, $ContentType, $Body, $TimeoutSec)
    if ($Uri -match '/api/tags$') {{ return [pscustomobject]@{{ models = @( {quote(payload)} | ConvertFrom-Json ) }} }}
    if ($Uri -match '/api/show$') {{
        if ($Method -ne 'Post') {{ throw 'Expected read-only show POST' }}
        $name = ([Text.Encoding]::UTF8.GetString($Body) | ConvertFrom-Json).model
        if ({str(unknown).lower().replace('true','$true').replace('false','$false')}) {{ return [pscustomobject]@{{ details = @{{}} }} }}
        if ($name -like '*embed*') {{ return [pscustomobject]@{{ capabilities = @('embedding') }} }}
        return [pscustomobject]@{{ capabilities = @('completion') }}
    }}
    throw 'Unexpected URL'
}}
"""


def doctor_mocks(directory, payload, exit_code):
    response = payload if isinstance(payload, str) else json.dumps(payload)
    return f"""
Set-Item -Path {quote('Function:' + str(directory / 'backend' / '.venv' / 'Scripts' / 'python.exe'))} -Value {{
    if (($args -join ' ') -ne '-m streamlingo.runtime_requirements') {{ throw 'UNEXPECTED PYTHON COMMAND' }}
    $global:LASTEXITCODE = {exit_code}
    {quote(response)}
}}
function Invoke-RestMethod {{
    param($Uri,$TimeoutSec)
    if ($Uri -match '/api/tags$') {{ return [pscustomobject]@{{ models = @([pscustomobject]@{{ name = 'chat:latest' }}) }} }}
    if ($Uri -eq 'http://127.0.0.1:8765/health') {{
        return [pscustomobject]@{{ status='ready'; protocol_version=1; mode='whisperlivekit'; translation='configured'; source_languages=@('en','zh','auto'); target_languages=@('zh-CN','en') }}
    }}
    throw 'UNEXPECTED NETWORK ATTEMPT'
}}
"""


def check_python_predicate():
    # Load only the actual Test-Python function through PowerShell's parser.
    # Each child Python executes its predicate with simulated version/bitness;
    # no setup top-level code, installers, network, models, or services run.
    directory = OUTPUT / "python predicate spaced path"
    for version, bits, expected in (("3, 12", 64, True), ("3, 12", 32, False),
                                    ("3, 10", 64, False), ("3, 14", 64, False), ("real", 64, True)):
        wrapper = directory / f"probe-{version.replace(', ', '-')}-{bits}.ps1"
        put(wrapper, f"""
$ErrorActionPreference = 'Stop'
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile({quote(ROOT / 'scripts' / 'setup.ps1')},[ref]$tokens,[ref]$errors)
$definition=$ast.Find({{param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Test-Python'}},$true)
Invoke-Expression $definition.Extent.Text
function Fixture-Python {{
    if ($args.Count -ne 2 -or $args[0] -ne '-c') {{ throw 'Unexpected Python probe arguments' }}
    $probe='import sys; sys.maxsize=2**({bits}-1)-1; sys.version_info=({version}); ' + $args[1]
    & {quote(sys.executable)} -c $probe
}}
$accepted=Test-Python {quote(sys.executable) if version == "real" else "'Fixture-Python'"}
if ($accepted -ne ${str(expected).lower()}) {{ throw 'Python version/bitness predicate accepted the wrong interpreter' }}
Write-Output 'PREDICATE_PASSED'
""")
        completed = subprocess.run([str(POWERSHELL), "-NoProfile", "-NonInteractive", "-File", str(wrapper)],
                                   capture_output=True, text=True, timeout=30)
        passed = completed.returncode == 0 and "PREDICATE_PASSED" in completed.stdout
        name = f"Python {version.replace(', ', '.')} {bits}-bit predicate"
        RESULTS.append(dict(name=name, passed=passed, exit_code=completed.returncode,
                            output=completed.stdout + completed.stderr))
        print(("PASS" if passed else "FAIL"), name)


def main():
    if sys.platform != "win32":
        raise SystemExit("Windows PowerShell 5.1 verification requires Windows")
    OUTPUT.mkdir(parents=True)
    for script in ("setup", "start", "stop", "doctor"):
        path = ROOT / "scripts" / f"{script}.ps1"
        command = f"$t=$null;$e=$null;[System.Management.Automation.Language.Parser]::ParseFile({quote(path)},[ref]$t,[ref]$e)|Out-Null;if($e.Count){{$e|ForEach-Object{{$_.Message}};exit 1}}"
        parsed = subprocess.run([str(POWERSHELL), "-NoProfile", "-Command", command], capture_output=True, text=True)
        RESULTS.append(dict(name=f"PowerShell 5.1 parses {script}", passed=parsed.returncode == 0,
                            output=parsed.stdout + parsed.stderr))

    check_python_predicate()

    directory = fixture("embedding rejected")
    run("embedding-only models fail before dependencies", directory, "setup", arguments="-NonInteractive",
        mocks=ollama(["embed:latest"]), expected="No installed text completion model")
    directory = fixture("chat filters embedding")
    output = run("one chat plus embedding selects chat without prompting", directory, "setup", arguments="-NonInteractive",
                 mocks=ollama(["chat:latest", "embed:latest"]), expected="FIXTURE_DEPENDENCY_BOUNDARY")
    RESULTS[-1]["passed"] &= "Translation model: chat:latest" in output
    RESULTS[-1]["passed"] &= all(text in output for text in ("64-bit Python 3.11-3.13", "NVIDIA GPU", "CUDA 12", "cuDNN 9", "docs/runtime-requirements.md"))
    directory = fixture("unknown capabilities")
    run("old Ollama without capabilities gives update guidance", directory, "setup", arguments="-NonInteractive",
        mocks=ollama(["chat:latest"], unknown=True), expected="update your existing Ollama")
    directory = fixture("ambiguous models")
    run("noninteractive ambiguous choice is explicit", directory, "setup", arguments="-NonInteractive",
        mocks=ollama(["chat:latest", "another:latest"]), expected="Multiple Ollama models")
    directory = fixture("explicit embedding")
    run("explicit embedding choice is rejected", directory, "setup", arguments="-NonInteractive -OllamaModel embed:latest",
        mocks=ollama(["chat:latest", "embed:latest"]), expected="does not report text completion support")
    directory = fixture("custom config", config={**config(), "ollamaUrl": "http://localhost:12345", "extensionId": "b" * 32})
    output = run("setup preserves configured URL and extension id", directory, "setup", arguments="-NonInteractive",
                 mocks=ollama(["chat:latest"]) + r"""
function Get-Command { param($Name)
    if ($OllamaUrl -ne 'http://localhost:12345' -or $ExtensionId -ne ('b' * 32)) { throw 'CONFIG_NOT_PRESERVED' }
    throw 'FIXTURE_DEPENDENCY_BOUNDARY'
}
""", expected="FIXTURE_DEPENDENCY_BOUNDARY")
    directory = fixture("source requires node", source=True)
    run("source checkout checks Node before dependency install", directory, "setup", arguments="-NonInteractive",
        mocks=ollama(["chat:latest"]) + "\nfunction Get-Command { return $null }\n", expected="requires Node.js 22+")
    directory = fixture("source ignores prebuilt", source=True)
    run("same-version source checkout still enters Node path", directory, "setup", arguments="-NonInteractive",
        mocks=ollama(["chat:latest"]) + r"""
function Get-Command { param($Name)
    if ($Name -in @('npm.cmd','node.exe')) { return [pscustomobject]@{ Name=$Name } }
    throw 'FIXTURE_DEPENDENCY_BOUNDARY'
}
function node.exe { $global:LASTEXITCODE=0; '22.0.0' }
""", expected="FIXTURE_DEPENDENCY_BOUNDARY")
    directory = fixture("partial release")
    (directory / "dist" / "extension" / "content.js").write_bytes(b"")
    # A missing manifest-listed entry must be rejected before any Python work.
    (directory / "dist" / "extension" / "content.js").unlink()
    run("release missing bundle asset rejected", directory, "setup", arguments="-NonInteractive",
        mocks=ollama(["chat:latest"]), expected="missing extension file 'content.js'")
    directory = fixture("bad config", config="{broken")
    run("start reports malformed config", directory, "start", expected="configuration is damaged")
    directory = fixture("no setup")
    run("start does not assume developer Qwen model", directory, "start", expected="No translation model is configured")
    directory = fixture("remote endpoint", config={**config(), "ollamaUrl": "http://remote.example:11434"})
    run("start rejects nonlocal configuration before network", directory, "start", expected="local HTTP(S) origin")
    directory = fixture("incomplete speech model", config=config())
    model_files(directory, omit="tokenizer.json")
    run("start catches missing tokenizer", directory, "start", expected="missing or empty tokenizer.json")
    directory = fixture("daily embedding reject", config={**config(), "ollamaModel": "embed:latest"})
    model_files(directory)
    run("start rejects selected embedding model", directory, "start", arguments="-Background",
        mocks=ollama(["embed:latest"]), expected="does not report text completion support")
    directory = fixture("daily no node", config=config())
    model_files(directory)
    output = run("daily background start quotes spaced paths without Node", directory, "start", arguments="-Background",
                 mocks=ollama(["chat:latest"]) + r"""
function Start-Process {
    param($FilePath,$ArgumentList,$WorkingDirectory,$WindowStyle,[switch]$PassThru,$RedirectStandardOutput,$RedirectStandardError)
    if ($WindowStyle -ne 'Hidden') { throw 'UNEXPECTED_VISIBLE_WINDOW' }
    if ($ArgumentList -notcontains ('"' + (Join-Path $WorkingDirectory 'models\whisper-base') + '"')) { throw 'SPACED_MODEL_PATH_NOT_QUOTED' }
    Write-Host 'FIXTURE_START_PROCESS_ONLY'
    return [pscustomobject]@{ Id=424242; StartTime=[DateTime]::UtcNow; HasExited=$false }
}
""", expected="FIXTURE_START_PROCESS_ONLY", success=True)

    directory = fixture("stale stop")
    put(directory / "output" / "service" / "process.json", json.dumps(dict(pid=424242, startedUtc="2026-10-13T00:00:00Z",
        python=str(directory / "backend" / ".venv" / "Scripts" / "python.exe"))))
    run("stale PID is cleared without stopping anything", directory, "stop", expected="already stopped", success=True)
    RESULTS[-1]["passed"] &= not (directory / "output" / "service" / "process.json").exists()
    directory = fixture("foreign stop")
    put(directory / "output" / "service" / "process.json", json.dumps(dict(pid=424242, startedUtc="2026-10-13T00:00:00Z", python="C:/another/python.exe")))
    run("foreign installation PID cannot be stopped", directory, "stop", expected="different installation")
    directory = fixture("recycled stop")
    put(directory / "output" / "service" / "process.json", json.dumps(dict(pid=424242, startedUtc="2026-10-13T00:00:00Z",
        python=str(directory / "backend" / ".venv" / "Scripts" / "python.exe"))))
    run("recycled PID cannot be stopped", directory, "stop", mocks=r"""
function Get-Process { return [pscustomobject]@{Id=424242; StartTime=[datetime]'2020-01-01'} }
function Get-CimInstance { return [pscustomobject]@{ExecutablePath=$taskRecord.python; CommandLine='python -m streamlingo.cli'} }
""", expected="no longer identifies")

    runtime_ok = dict(platform="win32", status="ok", missing_dlls=[],
                      message="DLL file check only; CUDA device availability and inference compatibility were not tested.")
    runtime_missing = dict(platform="win32", status="missing", missing_dlls=["cublas64_12.dll", "cudnn64_9.dll"],
                           message="Install CUDA 12 and cuDNN 9; see docs/runtime-requirements.md.")
    for name, payload, code, expected, expected_exit in (
        ("Doctor runtime ready", runtime_ok, 0, "[OK] Speech runtime files - DLL file check only", 0),
        ("Doctor missing DLLs", runtime_missing, 2, "Missing DLLs: cublas64_12.dll, cudnn64_9.dll", 1),
        ("Doctor rejects non-JSON", "not JSON", 0, "[CHECK] Speech runtime files", 1),
        ("Doctor rejects malformed schema", {**runtime_ok, "missing_dlls": None}, 0, "Invalid runtime-check JSON", 1),
        ("Doctor rejects success with failure exit", runtime_ok, 2, "Unexpected runtime-check status or exit code", 1),
        ("Doctor rejects missing with success exit", runtime_missing, 0, "Unexpected runtime-check status or exit code", 1),
        ("Doctor runtime not applicable", {**runtime_ok, "platform": "linux", "status": "not_applicable",
                                          "message": "Windows DLL file check does not apply to this platform."}, 0,
         "[OK] Speech runtime files - Windows DLL file check does not apply", 0),
    ):
        directory = fixture(name, config=config())
        model_files(directory)
        before_config = (directory / ".streamlingo.json").read_bytes()
        output = run(name, directory, "doctor", mocks=doctor_mocks(directory, payload, code),
                     expected=expected, expected_exit=expected_exit)
        RESULTS[-1]["passed"] &= "[OK] Subtitle service" in output and "[OK] Four translation modes" in output
        RESULTS[-1]["passed"] &= (directory / ".streamlingo.json").read_bytes() == before_config
        RESULTS[-1]["passed"] &= not (directory / "output" / "service").exists()
        if name == "Doctor missing DLLs":
            RESULTS[-1]["passed"] &= all(text in output for text in ("CUDA 12", "cuDNN 9", "docs/runtime-requirements.md"))

    directory = fixture("Doctor no Python", config=config())
    output = run("Doctor without venv skips the runtime command", directory, "doctor",
                 mocks=doctor_mocks(directory, "UNEXPECTED RUNTIME CALL", 99),
                 expected="[CHECK] Python environment", expected_exit=1)
    RESULTS[-1]["passed"] &= "Speech runtime files" not in output and "UNEXPECTED RUNTIME CALL" not in output

    for command, script in (("Setup", "setup"), ("Start", "start"), ("Stop", "stop"), ("Doctor", "doctor")):
        directory = fixture(f"cmd {command}")
        cmd = directory / f"{command}-StreamLingo.cmd"
        shutil.copy2(ROOT / cmd.name, cmd)
        put(directory / "scripts" / f"{script}.ps1", "exit 7")
        completed = subprocess.run(["cmd.exe", "/d", "/c", str(cmd)], input="\n", capture_output=True, text=True,
                                   errors="replace", timeout=30)
        RESULTS.append(dict(name=f"{command} CMD preserves failure exit code", passed=completed.returncode == 7,
                            exit_code=completed.returncode, output=completed.stdout + completed.stderr))
    report = OUTPUT / "report.json"
    report.write_text(json.dumps(RESULTS, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{sum(bool(item['passed']) for item in RESULTS)}/{len(RESULTS)} passed; report: {report}")
    raise SystemExit(0 if all(item["passed"] for item in RESULTS) else 1)


if __name__ == "__main__":
    main()
