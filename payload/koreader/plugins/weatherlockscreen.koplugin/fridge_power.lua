-- Probe real Kindle power integration; never assume every jailbroken Kindle has it.
local M={}
function M.prepare(device)
    if device.wakeup_mgr then return device.wakeup_mgr,'ready' end
    local ok,power=pcall(function()return device:getPowerDevice()end)
    if not ok or not power then return nil,'power_device_missing' end
    local supported_ok,supported=pcall(function()return device:supportsScreensaver()end)
    if not supported_ok or not supported then return nil,'native_screensaver_handoff' end
    if not power.lipc_handle then return nil,'power_lipc_unavailable' end
    if type(power.initWakeupMgr)=='function' then
        local initialized=pcall(function()power:initWakeupMgr()end)
        if initialized and device.wakeup_mgr then return device.wakeup_mgr,'ready_after_retry' end
    end
    return nil,'wakeup_manager_missing'
end
function M.refreshDelay(now,interval,settings)
    if not settings:readSetting("fridge_rtc_test_done") then return 120 end
    return require("fridge_model").nextDelay(now,interval)
end
function M.reasonLabel(reason)
    local labels={power_device_missing='Power service is unavailable',
        native_screensaver_handoff='The native Kindle system owns the sleep screen',
        power_lipc_unavailable='The Kindle power connection could not be opened',
        wakeup_manager_missing='The wake timer could not be initialized'}
    return labels[reason] or tostring(reason)
end
function M.writeDiagnostic(device,reason,path)
    local f=io.open(path,'a');if not f then return end
    local function probe(callback)local ok,v=pcall(callback);return ok and tostring(v) or 'probe_failed'end
    f:write(os.date('!%Y-%m-%dT%H:%M:%SZ'),' model=',tostring(device.model),
        ' reason=',reason,' screensaver=',probe(function()return device:supportsScreensaver()end),
        ' special_offers=',tostring(device.isSpecialOffers),
        ' lipc=',probe(function()return device:getPowerDevice().lipc_handle~=nil end),
        ' wakeup_mgr=',tostring(device.wakeup_mgr~=nil),'\n')
    f:close()
end
function M.restoreManualTimeout(settings)
    local saved=settings:readSetting('fridge_saved_settings')
    local original=type(saved)=='table' and saved.auto_suspend_timeout_seconds
    settings:saveSetting('auto_suspend_timeout_seconds',original and original.present and original.value or 900)
end
return M
