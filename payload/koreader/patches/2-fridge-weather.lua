--[[ Kindle Weather Station: KOReader startup patch (v1.1.0)
https://github.com/muffism/kindle-weather-station

Runs every time KOReader starts:
  1. First run only: picks the "Week" display style, a 30-minute dashboard
     refresh, hourly refreshes while asleep, the weather as the sleep screen,
     sleeping again 1 minute after you wake it, and "turn Wi-Fi on by itself"
     (set your city in the Weather Lockscreen menu).
  2. Clears the screen inversion left by the Kindle's own Dark Mode, so the
     screen is black on white. Turns the frontlight off.
  3. Applies koreader/settings-oneshot.lua if present (a Lua file returning
     { setting = value, ... }), then deletes it. Handy for changing settings
     over SSH, because KOReader overwrites settings.reader.lua while running.
  4. Auto mode:
       on the charger -> the live weather dashboard (Kindle stays awake);
       on battery     -> sleeps with the weather as its sleep screen and wakes
                         every hour to refresh it (about 25 s awake each time).
     Unplugging while the dashboard is open puts it to sleep the same way.
  5. Wi-Fi: turned on at every wake (the hourly refresh needs it), and off
     again after 5 minutes awake, unless an SSH session is open.
  6. Logs the battery to koreader/battery-log.txt at every sleep and wake,
     and every 5 minutes while awake.

Flag files (empty files in the Kindle's main folder):
  weather-station-off   don't open the dashboard / don't sleep at start
  wifi-always-on        never switch Wi-Fi off after 5 minutes
  frontlight-keep       leave the frontlight alone
Tap the screen to leave the dashboard. ]]
local logger = require("logger")
local UIManager = require("ui/uimanager")
local Event = require("ui/event")
local Device = require("device")
local lfs = require("libs/libkoreader-lfs")

local function flag(name) return lfs.attributes("/mnt/us/" .. name, "mode") ~= nil end

local Control=dofile("plugins/weatherlockscreen.koplugin/fridge_control.lua")
if not Control.enabled() then
    Control.stop() -- restore preferences after disabling via USB/scriptlet
    return
end
Control.enter()

-- 2a. Kindle Dark Mode leaves the framebuffer hardware-inverted; KOReader keeps
--     that unless its own night mode is on. Clear it for a paper look.
if not G_reader_settings:isTrue("night_mode") and Device.screen.getHWNightmode
    and Device.screen:getHWNightmode() then
    Device.screen:setHWNightmode(false)
    logger.info("weather-station: cleared hardware screen inversion")
end

-- 2b. Frontlight off: an e-ink weather display doesn't need it, and it's one of
--     the biggest battery drains. Again 10 s later in case the Kindle restores it.
local function frontlightOff()
    if flag("frontlight-keep") then return end
    pcall(function()
        local pd = Device:getPowerDevice()
        if pd:isFrontlightOn() then
            pd:turnOffFrontlight()
            logger.info("weather-station: frontlight off")
        end
    end)
end
frontlightOff()
UIManager:scheduleIn(10, frontlightOff)

-- 3. one-shot settings file
do
    local f = "settings-oneshot.lua"
    if lfs.attributes(f, "mode") then
        local ok, t = pcall(dofile, f)
        if ok and type(t) == "table" then
            for k, v in pairs(t) do G_reader_settings:saveSetting(k, v) end
            G_reader_settings:flush()
            logger.info("weather-station: applied settings-oneshot.lua")
        end
        os.remove(f)
    end
end

-- Wi-Fi up at start
UIManager:scheduleIn(2, function()
    local NetworkMgr = require("ui/network/manager")
    if not NetworkMgr:isOnline() then
        pcall(function() NetworkMgr:runWhenOnline(function() end) end)
    end
end)

-- 4. auto mode helpers
local function onExternalPower()
    local ok, v = pcall(function()
        local pd = Device:getPowerDevice()
        return pd:isCharging() or (pd.isCharged and pd:isCharged())
    end)
    return ok and v or false
end
local function weatherPlugin()
    local RUI = package.loaded["apps/reader/readerui"]
    local FM = package.loaded["apps/filemanager/filemanager"]
    local ui = (RUI and RUI.instance) or (FM and FM.instance)
    return ui and ui.weatherlockscreen
end
local function sleepWithWeather(reason)
    logger.info("weather-station: going to sleep with the weather screen (" .. reason .. ")")
    local wl = weatherPlugin()
    if not wl or not wl.wakeup_mgr then
        logger.warn("KindleWeather: automatic sleep skipped; no wakeup manager")
        return false
    end
    if wl.dashboard_mode_enabled then
        UIManager:broadcastEvent(Event:new("ToggleWeatherDashboard"))   -- close dashboard first
    end
    UIManager:scheduleIn(2, function() UIManager:suspend() end)
end

-- 5 + 6. watchdog (every 30 s while awake), Wi-Fi at wake, battery log
do
    local WIFI_ON_MAX = 90
    local wifi_on_secs = 0
    local tick = 0

    -- the battery's sysfs folder differs between Kindle models
    local BAT
    pcall(function()
        for e in lfs.dir("/sys/class/power_supply") do
            local d = "/sys/class/power_supply/" .. e .. "/"
            if e:sub(1, 1) ~= "." and lfs.attributes(d .. "capacity", "mode") then
                BAT = d
                break
            end
        end
    end)
    local function readLine(f)
        local h = f and io.open(f, "r")
        if not h then return "?" end
        local v = h:read("*l"); h:close()
        return v or "?"
    end
    local last_log
    local function batteryLog(tag)
        local key = os.date("%m-%d %H:%M") .. tag   -- at most one line per minute and tag
        if key == last_log then return end
        last_log = key
        local h = io.open("/mnt/us/koreader/battery-log.txt", "a")
        if h then
            h:write(os.date("%m-%d %H:%M"), " ", readLine(BAT and BAT .. "capacity"), "% ",
                readLine(BAT and BAT .. "current_now"), "uA ", readLine(BAT and BAT .. "status"),
                " ", tag, "\n")
            h:close()
        end
    end
    local function sshSessionActive()
        -- KOReader's SSH server (dropbear) forks one process per client
        local p = io.popen("pidof dropbear 2>/dev/null")
        local out = p and p:read("*a") or ""
        if p then p:close() end
        local n = 0
        for _ in out:gmatch("%d+") do n = n + 1 end
        return n > 1
    end
    local function watch()
        if not Control.enabled() then return end
        local NetworkMgr = require("ui/network/manager")
        local ok, on = pcall(function() return NetworkMgr:isWifiOn() end)
        on = ok and on or false
        local ssh = sshSessionActive()
        if ssh then
            -- someone is connected: count it as activity so the Kindle stays awake
            pcall(function() UIManager.event_hook:execute("InputEvent") end)
        end
        -- count awake time only: time asleep must not count towards the 5 minutes
        if on then
            wifi_on_secs = wifi_on_secs + 30
            if wifi_on_secs >= WIFI_ON_MAX and not flag("wifi-always-on") and not ssh then
                logger.info("weather-station: Wi-Fi on for 90 s awake, turning it off")
                pcall(function() NetworkMgr:turnOffWifi() end)
                wifi_on_secs = 0
            end
        else
            wifi_on_secs = 0
        end
        local wl = weatherPlugin()
        if wl and wl.wakeup_mgr and wl.dashboard_mode_enabled and not onExternalPower()
            and not flag("weather-station-off") then
            sleepWithWeather("unplugged")
        end
        if tick % 10 == 0 then batteryLog(on and "wifi" or "-") end
        tick = tick + 1
        UIManager:scheduleIn(30, watch)
    end
    UIManager:scheduleIn(30, watch)

    -- Timers don't run while asleep, so hook the Kindle's own sleep and wake
    -- callbacks (each hourly refresh is a wake + sleep).
    for name, tag in pairs({ readyToSuspend = "sleep", wakeupFromSuspend = "wake" }) do
        local orig = Device[name]
        if type(orig) == "function" then
            Device[name] = function(...)
                pcall(batteryLog, tag)
                wifi_on_secs = 0
                if tag == "sleep" and not flag("wifi-always-on") then
                    pcall(function() require("ui/network/manager"):turnOffWifi() end)
                end
                local r = { orig(...) }
                if tag == "wake" then
                    -- the hourly refresh doesn't turn Wi-Fi on by itself
                    UIManager:nextTick(function()
                        pcall(function()
                            local NetworkMgr = require("ui/network/manager")
                            if not NetworkMgr:isWifiOn() then
                                logger.info("weather-station: woke with Wi-Fi off, turning it on")
                                NetworkMgr:turnOnWifi()
                            end
                        end)
                    end)
                end
                return unpack(r)
            end
        else
            logger.warn("weather-station: Device." .. name .. " not found (not a Kindle?)")
        end
    end
end

if flag("weather-station-off") then
    logger.info("weather-station: auto mode disabled by flag file")
    return
end

UIManager:scheduleIn(4, function()
    local wl=weatherPlugin()
    if not wl then
        logger.err("KindleWeather: plugin did not initialize; auto sleep cancelled")
        require("fridge_power").restoreManualTimeout(G_reader_settings)
        return
    end
    if not wl.wakeup_mgr then
        local Power=require("fridge_power")
        Power.restoreManualTimeout(G_reader_settings)
        local reason=G_reader_settings:readSetting("fridge_rtc_reason") or "wakeup_manager_missing"
        logger.warn("KindleWeather: manual mode",reason)
        UIManager:show(require("ui/widget/infomessage"):new{
            text="Scheduled wake is unavailable: "..Power.reasonLabel(reason)..". Automatic sleep is disabled.",timeout=10})
        return
    end
    logger.info("KindleWeather: opening initial dashboard")
    UIManager:broadcastEvent(Event:new("ToggleWeatherDashboard"))
    if not onExternalPower() then
        -- Show the result first, then enter the weather sleep screen.
        UIManager:scheduleIn(20, function() sleepWithWeather("started on battery") end)
        return
    end
    -- The Kindle status-bar clock can get drawn over us during boot;
    -- a full repaint a little later wipes it.
    UIManager:scheduleIn(12, function() UIManager:setDirty("all", "full") end)
end)
