-- Standstill launcher: serves the web app on localhost and opens it in Chrome.
-- Lives next to the "web" folder; move the whole folder wherever you like.

set myPath to POSIX path of (path to me)
if myPath ends with "/" then set myPath to text 1 thru -2 of myPath
set projectDir to do shell script "dirname " & quoted form of myPath
set webDir to projectDir & "/web"
set thePort to "8777"
set theURL to "http://localhost:" & thePort & "/"

if (do shell script "test -f " & quoted form of (webDir & "/index.html") & " && echo yes || echo no") is "no" then
	display dialog "Can't find the 'web' folder next to this app." buttons {"OK"} default button 1 with icon stop
	return
end if

-- Start the little static server only if it isn't already running.
set isUp to do shell script "curl -s -o /dev/null -m 1 " & theURL & " && echo yes || echo no"
if isUp is "no" then
	-- The subshell plus </dev/null fully detaches the server; without it
	-- "do shell script" waits forever on the inherited pipe.
	do shell script "cd " & quoted form of webDir & " && (/usr/bin/python3 -m http.server " & thePort & " --bind 127.0.0.1 </dev/null >/dev/null 2>&1 &) ; echo started"
	repeat 20 times
		delay 0.25
		set isUp to do shell script "curl -s -o /dev/null -m 1 " & theURL & " && echo yes || echo no"
		if isUp is "yes" then exit repeat
	end repeat
end if

if isUp is "no" then
	display dialog "Couldn't start the local server on port " & thePort & "." buttons {"OK"} default button 1 with icon stop
	return
end if

try
	do shell script "open -a " & quoted form of "/Applications/Google Chrome.app" & " " & quoted form of theURL
on error
	do shell script "open " & quoted form of theURL
end try
