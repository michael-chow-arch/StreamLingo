# Original synthetic speech, including intentional real repetition. No audio
# capture, network request, model load, GPU use, or service access.
param([string]$OutputDirectory = 'output/regression-repetition')
$ErrorActionPreference = 'Stop'
$taskOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $taskOutput | Out-Null
$taskText = 'Please wait. Please wait. The next part of our demonstration will begin in a moment. This is a very, very important point. A speaker may repeat a phrase on purpose, and the subtitles should preserve those spoken words. Now we can continue with a different sentence about the weather outside.'
$taskText | Set-Content -LiteralPath (Join-Path $taskOutput 'reference.txt') -Encoding utf8
Add-Type -AssemblyName System.Speech
$taskSynth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $taskSynth.SelectVoice('Microsoft Zira Desktop')
    $taskSynth.Rate = 0
    $taskFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
    $taskSynth.SetOutputToWaveFile((Join-Path $taskOutput 'english-repeat.wav'), $taskFormat)
    $taskSynth.Speak($taskText)
} finally {
    $taskSynth.Dispose()
}
Write-Output "Synthetic repetition fixture created: $taskOutput\english-repeat.wav"
