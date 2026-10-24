# Registra una tarea programada de Windows que corre el bot cada 15 minutos.
# Ejecutar desde la carpeta donde quedó dune_imax_bot.py:
#   powershell -ExecutionPolicy Bypass -File instalar_tarea.ps1
# Para desinstalar:
#   Unregister-ScheduledTask -TaskName "DuneImaxBot" -Confirm:$false

$script = Join-Path $PSScriptRoot "dune_imax_bot.py"
$pythonw = (Get-Command pythonw).Source

$action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName "DuneImaxBot" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Avisa cuando hay entradas de Dune 3 en el IMAX de Showcase" -Force

Write-Host "Tarea 'DuneImaxBot' registrada: corre cada 15 minutos usando $script"
