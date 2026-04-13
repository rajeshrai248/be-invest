# Register Windows Task Scheduler entry for the weekly broker fee email.
# Run as: powershell -ExecutionPolicy Bypass -File scripts\register_weekly_email_task.ps1
# Unregister with: Unregister-ScheduledTask -TaskName 'BeInvest-WeeklyEmail' -Confirm:$false

$ErrorActionPreference = 'Stop'

$py      = 'C:\Users\rajes\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\python.exe'
$script  = 'C:\Users\rajes\PycharmProjects\be-invest - claude\scripts\send_weekly_email.py'
$workdir = 'C:\Users\rajes\PycharmProjects\be-invest - claude'

$action = New-ScheduledTaskAction `
    -Execute $py `
    -Argument ('"{0}"' -f $script) `
    -WorkingDirectory $workdir

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 9:00am

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName 'BeInvest-WeeklyEmail' `
    -Description 'Weekly broker fee comparison email (be-invest)' `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Force | Select-Object TaskName, State
