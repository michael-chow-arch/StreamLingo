# Synthesize original test paragraphs only. No browser, microphone or model server.
param(
    [Parameter(Mandatory=$true)][string]$Corpus,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateSet('en','zh','both')][string]$Languages = 'both',
    [ValidateRange(1,86400)][double]$MinimumSeconds = 1800
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$taskCorpus = Get-Content -LiteralPath $Corpus -Raw -Encoding UTF8 | ConvertFrom-Json
$taskOutput = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
function Read-WaveDataLength([string]$Path) {
    $reader = New-Object IO.BinaryReader([IO.File]::OpenRead($Path))
    try {
        if ([Text.Encoding]::ASCII.GetString($reader.ReadBytes(4)) -ne 'RIFF') { throw 'Invalid RIFF file' }
        $null = $reader.ReadUInt32()
        if ([Text.Encoding]::ASCII.GetString($reader.ReadBytes(4)) -ne 'WAVE') { throw 'Invalid WAV file' }
        while ($reader.BaseStream.Position + 8 -le $reader.BaseStream.Length) {
            $id = [Text.Encoding]::ASCII.GetString($reader.ReadBytes(4)); $size = $reader.ReadUInt32()
            if ($id -eq 'data') { return $size }
            $null = $reader.BaseStream.Seek($size + ($size % 2), [IO.SeekOrigin]::Current)
        }
        throw 'No WAV data chunk'
    } finally { $reader.Dispose() }
}
$selectedLanguages = if ($Languages -eq 'both') { @('en','zh') } else { @($Languages) }
foreach ($language in $selectedLanguages) {
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $records = New-Object Collections.Generic.List[object]
    $seconds = 0.0
    $languageOutput = Join-Path $taskOutput $language
    New-Item -ItemType Directory -Path $languageOutput -Force | Out-Null
    try {
        $culture = if ($language -eq 'en') { 'en-US' } else { 'zh-CN' }
        $voices = @($synth.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -eq $culture })
        if (-not $voices.Count) { throw "No enabled System.Speech $culture voice. Install the Windows desktop speech voice before preparing this fixture." }
        $preferred = if ($language -eq 'en') { 'Microsoft Zira Desktop' } else { 'Microsoft Huihui Desktop' }
        $voice = @($voices | Where-Object { $_.VoiceInfo.Name -eq $preferred } | Select-Object -First 1)
        if (-not $voice.Count) { $voice = @($voices | Select-Object -First 1) }
        $synth.SelectVoice($voice[0].VoiceInfo.Name)
        $synth.Rate = 0
        $format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
        $index = 0
        foreach ($paragraph in $taskCorpus.$language) {
            if ($seconds -ge $MinimumSeconds) { break }
            $index++
            $path = Join-Path $languageOutput ('paragraph-{0:D4}.wav' -f $index)
            $synth.SetOutputToWaveFile($path, $format)
            $synth.Speak($paragraph)
            $synth.SetOutputToNull()
            $duration = (Read-WaveDataLength $path) / 32000.0
            if ($duration -le 0) { throw 'Empty synthesized paragraph' }
            $records.Add(@{ index=$index; text=$paragraph; file=[IO.Path]::GetFileName($path); start_s=$seconds; duration_s=$duration })
            $seconds += $duration
            if ($index % 10 -eq 0) { Write-Host ("Prepared {0}: {1} paragraphs, {2:N1} audio seconds" -f $language,$index,$seconds) }
        }
        if ($seconds -lt $MinimumSeconds) { throw "Corpus exhausted before $MinimumSeconds seconds for $language" }
        @{ language=$language; voice=$synth.Voice.Name; sample_rate=16000; channels=1; sample_width=2;
           duration_s=$seconds; minimum_seconds=$MinimumSeconds; paragraphs=@($records.ToArray());
           source='Original controlled System.Speech synthesis; no human recording or audio loop' } |
            ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $languageOutput 'paragraphs.json') -Encoding UTF8
        Write-Host ("Completed {0}: {1:N1}s using {2}" -f $language,$seconds,$synth.Voice.Name)
    } finally { $synth.Dispose() }
}
