--!nonstrict
-- GPU Screen Recorder - bar widget (thin presentation client).
--
-- The recording logic lives in the [[service]] (recorder_service.luau), which runs
-- for the whole session. This widget only reflects the published "status" and
-- drives the recorder by writing to the "command" channel.
--
-- Click mapping:
--   Left click   - stop an active capture, or start recording
--   Right click  - open the newest recording (patched); with a live replay
--                  buffer it saves the buffer instead, as before
--   Middle click - save replay buffer

local state = "idle" -- idle | pending | recording | replay_pending | replaying
local available = false
local RECORDING_STATES = { "recording", "pending" }
local REPLAY_STATES = { "replaying", "replay_pending" }
local PENDING_STATES = { "pending", "replay_pending" }

local function send(action)
    noctalia.state.set("command", { action = action, focusedOutputName = noctalia.focusedOutputName() })
end

-- ── open the newest recording (patched) ─────────────────────────────────
local function shellQuote(value)
    return "'" .. value:gsub("'", [["'"']]) .. "'"
end

-- Same resolution the service uses for its output path.
local function recordingDirectory()
    local configured = noctalia.getConfig("directory")
    local dir = noctalia.expandPath(if configured == nil or configured == "" then "~/Videos/Recordings" else configured)
    if dir:sub(-1) ~= "/" then dir ..= "/" end
    return dir
end

-- `ls -t` orders by mtime, so a custom filename_pattern cannot break "newest".
local function openLatestRecording()
    local dir = recordingDirectory()
    noctalia.runAsync(`ls -t {shellQuote(dir)}*.mp4 2>/dev/null | head -n 1`, function(result)
        local path = noctalia.string.trim(result.stdout or "")
        if result.exitCode ~= 0 or path == "" then
            noctalia.notifyError(noctalia.tr("notify.recording-failed"), "No recordings in " .. dir)
            return
        end
        noctalia.runAsync({ "xdg-open", path })
    end)
end

-- Glyph per state, configurable. The fallback passed to each lookup is the
-- value this widget used before the settings existed, so an unset or blank
-- glyph keeps the previous appearance.
local function glyphFor(key, fallback)
    local configured = noctalia.getConfig(key)
    if type(configured) == "string" and configured ~= "" then
        return configured
    end
    return fallback
end

local function applyStatus(status)
    if type(status) == "table" then
        state = status.state or "idle"
        available = if status.available then true else false
    end

    local hideInactive = noctalia.getConfig("hide_inactive")

    if not available then
        barWidget.setGlyph(glyphFor("glyph_unavailable", "video-off"))
        barWidget.setGlyphColor("on_surface_variant")
        barWidget.setVisible(not hideInactive)
        return
    end

    if state == "recording" then
        barWidget.setGlyph(glyphFor("glyph_recording", "video"))
        barWidget.setGlyphColor("error")
        barWidget.setColor("error")
        barWidget.setVisible(true)
    elseif table.find(PENDING_STATES, state) then
        barWidget.setGlyph(glyphFor("glyph_pending", "video"))
        barWidget.setGlyphColor("primary")
        barWidget.setColor("primary")
        barWidget.setVisible(true)
    elseif state == "replaying" then
        barWidget.setGlyph(glyphFor("glyph_replaying", "repeat"))
        barWidget.setGlyphColor("secondary")
        barWidget.setColor("secondary")
        barWidget.setVisible(true)
    else
        barWidget.setGlyph(glyphFor("glyph_idle", "video"))
        barWidget.setGlyphColor("on_surface")
        barWidget.setVisible(not hideInactive)
    end
end

function onClick()
    if not available then return end
    if table.find(RECORDING_STATES, state) then
        send("stop")
    elseif table.find(REPLAY_STATES, state) then
        send("replay-stop")
    elseif state == "idle" then
        send("start")
    end
end

function onRightClick()
    if not available then return end
    if state == "replaying" then
        send("replay-save")
    elseif state == "replay_pending" then
        send("replay-stop")
    elseif state == "idle" then
        openLatestRecording()
    end
end

function onMiddleClick()
    if state == "replaying" then
        send("replay-save")
    end
end

-- Sync the current status on load, then track changes.
applyStatus(noctalia.state.get("status"))
noctalia.state.watch("status", applyStatus)
