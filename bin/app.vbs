' 콘솔 창 없이 프로그램 실행. .env 를 읽어 환경변수로 올린 뒤 pythonw 로 창만 띄운다.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
sh.CurrentDirectory = root
Set env = sh.Environment("Process")
If fso.FileExists(root & "\.env") Then
  Set f = fso.OpenTextFile(root & "\.env", 1, False, -1)
  Do Until f.AtEndOfStream
    line = Trim(f.ReadLine)
    If line <> "" And Left(line, 1) <> "#" And InStr(line, "=") > 0 Then
      env(Left(line, InStr(line, "=") - 1)) = Mid(line, InStr(line, "=") + 1)
    End If
  Loop
  f.Close
End If
env("PYTHONIOENCODING") = "utf-8"
sh.Run """" & root & "\.venv\Scripts\pythonw.exe"" -m kolis_tool.app", 0, False
