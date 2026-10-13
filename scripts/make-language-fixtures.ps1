# Original synthetic speech for local model verification; no microphone/browser capture.
param([string]$OutputDirectory = 'output/languages')
$ErrorActionPreference = 'Stop'
$taskOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $taskOutput | Out-Null
Add-Type -AssemblyName System.Speech
$taskFixtures = @(
    @{ Name='english'; Voice='Microsoft Zira Desktop'; Text='Welcome to our language workshop. Today we will learn how to build a small garden. Put the blue flowers beside the window. Give them fresh water every morning.' },
    @{ Name='chinese'; Voice='Microsoft Huihui Desktop'; Text='欢迎来到我们的语言课堂。今天我们学习如何布置一个小花园。请把蓝色的花放在窗户旁边。每天早上给它们浇水。' }
)
foreach ($taskFixture in $taskFixtures) {
    $taskSynth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $taskSynth.SelectVoice($taskFixture.Voice)
        $taskFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
        $taskSynth.SetOutputToWaveFile((Join-Path $taskOutput "$($taskFixture.Name).wav"), $taskFormat)
        $taskSynth.Speak($taskFixture.Text)
        $taskFixture.Text | Set-Content -LiteralPath (Join-Path $taskOutput "$($taskFixture.Name).txt") -Encoding utf8
    } finally { $taskSynth.Dispose() }
}
Write-Output "Created original English and Chinese synthetic speech: $taskOutput"
