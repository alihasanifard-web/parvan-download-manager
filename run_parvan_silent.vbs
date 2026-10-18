Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\V I S I O N\parvan-download-manager"
WshShell.Run """C:\Users\V I S I O N\AppData\Local\hermes\installs\29bb8c0b3ad4b6fa\environments\4d12117631fd4eb185d5850249a8d4c2\venv\Scripts\python.exe"" app.py", 0, False
