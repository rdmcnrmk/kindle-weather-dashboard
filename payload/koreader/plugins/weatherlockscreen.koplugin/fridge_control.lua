-- Preserve the reader's preferences while the dedicated panel is active.
local C={flag='/mnt/us/hava-panosu-enabled'}
local config=dofile('plugins/weatherlockscreen.koplugin/fridge_config.lua')
function C.enabled()
    local f=io.open(C.flag,'r');if f then f:close();return true end
    return false
end
function C.enter()
    local values={screensaver_type='weather',weather_display_style='week',weather_temp_scale='C',
        weather_location=config.latitude..','..config.longitude,weather_location_name=config.city,
        weather_override_rotation=true,weather_orientation=0,night_mode=false,
        weather_periodic_refresh_dashboard=config.refresh_seconds,
        weather_periodic_refresh_dashboard_charging=config.refresh_seconds,
        weather_periodic_refresh_rtc=config.refresh_seconds,
        weather_periodic_refresh_rtc_charging=config.refresh_seconds,
        weather_active_sleep_min_battery=config.minimum_battery,
        auto_suspend_timeout_seconds=config.interactive_idle_seconds or 300,wifi_enable_action='turn_on',wifi_disable_action='leave_on'}
    if not G_reader_settings:readSetting('fridge_saved_settings') then
        local saved={}
        for k in pairs(values) do
            local v=G_reader_settings:readSetting(k)
            saved[k]={present=v~=nil,value=v}
        end
        G_reader_settings:saveSetting('fridge_saved_settings',saved)
    end
    for k,v in pairs(values) do G_reader_settings:saveSetting(k,v) end
    G_reader_settings:flush()
end
function C.stop()
    os.remove(C.flag)
    local saved=G_reader_settings:readSetting('fridge_saved_settings')
    if type(saved)=='table' then
        for k,v in pairs(saved) do
            if v.present then G_reader_settings:saveSetting(k,v.value) else G_reader_settings:delSetting(k) end
        end
        G_reader_settings:delSetting('fridge_saved_settings')
        G_reader_settings:flush()
    end
end
return C
