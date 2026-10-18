Set oWS = WScript.CreateObject("WScript.Shell")
sDesk = oWS.SpecialFolders("Desktop")
Set oLink = oWS.CreateShortcut(sDesk & "\Parvan Download Manager.lnk")
oLink.TargetPath = "C:\Users\V I S I O N\parvan-download-manager\run_parvan.cmd"
oLink.WorkingDirectory = "C:\Users\V I S I O N\parvan-download-manager"
oLink.Description = "Parvan Download Manager - پروان دانلود منیجر"
oLink.Save
