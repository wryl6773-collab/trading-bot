' Starts the bot without a black console window. Closing the dashboard window also stops the bot.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
sh.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)
sh.Run "cmd /c pythonw app.py || pyw app.py", 0, False
