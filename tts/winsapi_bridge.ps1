param(
    [Parameter(Mandatory = $true)][string]$Text,
    [Parameter(Mandatory = $true)][string]$Path
)
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $speaker.Rate = 0
    $speaker.SetOutputToWaveFile($Path)
    $speaker.Speak($Text)
}
finally {
    $speaker.Dispose()
}
