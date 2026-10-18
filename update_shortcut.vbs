Set oWS = WScript.CreateObject("WScript.Shell")
sDesk = oWS.SpecialFolders("Desktop")
Set oLink = oWS.CreateShortcut(sDesk & "\Parvan Download Manager.lnk")
oLink.TargetPath = "C:\Users\V I S I O N\parvan-download-manager\dist\ParvanDownloadManager\ParvanDownloadManager.exe"
oLink.WorkingDirectory = "C:\Users\V I S I O N\parvan-download-manager\dist\ParvanDownloadManager"
oLink.IconLocation = "C:\Users\V I S I O N\parvan-download-manager\icon.ico, 0"
oLink.Description = "Parvan Download Manager - پروان دانلود منیجر"
oLink.Save
