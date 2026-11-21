-- Open-Meteo-only provider; no third-party API keys. AGPL-3.0-or-later.
local Model=require('fridge_model')
local Config=require('fridge_config')
local Storage=require('datastorage')
local logger=require('logger')
local S={}
local cache_file=Storage:getDataDir()..'/cache/fridge-weather-v1.json'
local key=table.concat({Config.latitude,Config.longitude,Config.timezone},':')
function S.url()
    return string.format('https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f',Config.latitude,Config.longitude)
        ..'&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,is_day'
        ..'&hourly=precipitation_probability,snowfall'
        ..'&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset'
        ..'&timezone=Europe%2FAmsterdam&timeformat=unixtime&forecast_days=5&wind_speed_unit=kmh'
end
local function decode(body)
    if type(body)~='string' then return nil end
    local ok,t=pcall(require('json').decode,body)
    return ok and t or nil
end
function S.readCache(now)
    local f=io.open(cache_file,'r')
    if not f then return nil end
    local bytes=f:read('*a');f:close()
    local c=decode(bytes)
    if type(c)~='table' or c.key~=key or not Model.valid(c.data) or not Model.number(c.fetched) then return nil end
    local age=now-c.fetched
    if age<0 or age>48*3600 then return nil end
    return c
end
local function writeCache(data,now)
    require('util').makePath(Storage:getDataDir()..'/cache')
    local f=io.open(cache_file..'.tmp','w')
    if not f then return end
    local ok,bytes=pcall(require('json').encode,{key=key,fetched=now,data=data})
    if not ok then f:close();os.remove(cache_file..'.tmp');return end
    f:write(bytes);f:close()
    os.rename(cache_file..'.tmp',cache_file)
end
function S.httpGet(url)
    local sink={}
    local util_ok,socketutil=pcall(require,'socketutil')
    if util_ok then socketutil:set_timeout(10,20) end
    local ok,code=pcall(function()
        local https=require('ssl.https')
        local _,status=https.request{url=url,sink=require('ltn12').sink.table(sink)}
        return tonumber(status)
    end)
    if util_ok then socketutil:reset_timeout() end
    if not ok or code~=200 then
        logger.warn('HavaPanosu: forecast request failed',ok and code or 'network error')
        return nil
    end
    return table.concat(sink)
end
function S.fetch(plugin)
    local now=os.time()
    local c=S.readCache(now)
    if plugin and plugin.prefer_cache then
        return c and c.data,c and c.fetched
    end
    if c and now-c.fetched<20*60 and not (plugin and plugin.refresh) then
        if plugin then plugin.refresh=false end
        return c.data,c.fetched
    end
    local data=decode(S.httpGet(S.url()))
    if Model.valid(data) then
        writeCache(data,now)
        if plugin then plugin.refresh=false end
        logger.info('HavaPanosu: forecast updated')
        return data,now
    end
    return c and c.data,c and c.fetched
end
return S
