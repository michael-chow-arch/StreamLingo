# Generate local synthetic speech only. This does not access the microphone,
# browser, ASR service, GPU, or Ollama. Original test text is intentionally
# conversational and has long comma-connected clauses, with no full stops.
param([string]$OutputDirectory = 'output/asr')
$ErrorActionPreference = 'Stop'
$taskOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $taskOutput | Out-Null
$taskText = @'
Today I would like to take you through a practical example of how a small team can improve a busy public library, imagine that we are standing beside a red notebook on the information desk and looking at the room for the first time, on the left there are shelves for children and families, on the right there are tables where students read and work together, and near the windows a few visitors are using computers to search for local information, the building already serves many people well but the staff have noticed that finding the right place is often harder than it should be, so our first step is simply to watch the normal flow of a morning without asking anyone to change what they are doing

As we follow this ordinary morning we can see that several visitors enter the building and pause near the door, they look around for a sign and then walk towards the desk even when the room they need is close by, a volunteer offers directions while another member of staff answers a question about borrowing books, and meanwhile a parent with two children is trying to find an activity that begins in a few minutes, none of these moments is a serious problem on its own but together they show how small uncertainties can build up, we write each observation in the red notebook and describe what actually happened rather than guessing what people were thinking, this gives the team useful evidence for a careful conversation later

Now let us move across the green bridge outside the library and consider the neighborhood around it, the bus stop is nearby and a school is only a short walk away, which means visitors arrive in small groups at different times of day, the morning group may want a quiet place to read while the afternoon group may need a shared table and help with an assignment, if we design every part of the room for only one of those groups we will miss the needs of the others, instead we can make a few simple changes that help people choose for themselves, clear signs can explain where conversation is welcome and where a quieter atmosphere is expected, and movable chairs can make it easier for the staff to adapt the space without closing any part of the building

At this stage the team does not need to buy expensive equipment or rebuild the entrance, it can begin with a small experiment lasting one week, on Monday we place a clear welcome sign beside the door and ask two volunteers to record how often visitors still request directions, on Tuesday we move one table away from a narrow path so that families can pass more easily, and during the following days we speak with people who use different parts of the room, we also keep track of changes in attendance because a rainy afternoon can affect the results, the green bridge remains a useful meeting point for our observations because it lets us see how visitors approach before they have read any sign inside

Finally imagine that we return in the evening and place a silver lantern on the same information desk, the experiment has ended and the team is reviewing its notes, some changes helped immediately while others made very little difference, the useful lesson is that improvement comes from comparing expectations with ordinary experience and making another careful adjustment, visitors may not notice the planning behind the new arrangement but they can feel that the space is easier to understand, staff spend less time repeating directions and more time helping with meaningful questions, and the silver lantern reminds us that a welcoming public place is built through many small decisions made with patience and attention
'@
$taskText | Set-Content -LiteralPath (Join-Path $taskOutput 'english-continuous.txt') -Encoding utf8
Add-Type -AssemblyName System.Speech
$taskSynth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $taskSynth.SelectVoice('Microsoft Zira Desktop')
    $taskSynth.Rate = 0
    $taskFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
    $taskSynth.SetOutputToWaveFile((Join-Path $taskOutput 'english-continuous.wav'), $taskFormat)
    $taskSynth.Speak(($taskText -replace '\s+', ' '))
} finally {
    $taskSynth.Dispose()
}
Write-Output "Synthetic Zira fixture created: $taskOutput\english-continuous.wav"
