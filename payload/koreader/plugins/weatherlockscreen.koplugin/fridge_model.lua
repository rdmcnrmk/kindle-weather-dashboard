-- Weather Dashboard: pure forecast/date logic. AGPL-3.0-or-later.
local M = {}
local months = {"January","February","March","April","May","June","July","August","September","October","November","December"}
local months_upper = {"JANUARY","FEBRUARY","MARCH","APRIL","MAY","JUNE","JULY","AUGUST","SEPTEMBER","OCTOBER","NOVEMBER","DECEMBER"}
local weekdays = {"Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"}
local codes = {
 [0]={"Clear","clear-day","clear-night"}, [1]={"Mostly clear","partly-day","partly-night"},
 [2]={"Partly cloudy","partly-day","partly-night"}, [3]={"Overcast","cloudy"},
 [45]={"Fog","fog"}, [48]={"Freezing fog","fog"},
 [51]={"Light drizzle","drizzle"},[53]={"Drizzle","drizzle"},[55]={"Heavy drizzle","drizzle"},
 [56]={"Freezing drizzle","sleet"},[57]={"Freezing drizzle","sleet"},
 [61]={"Light rain","rain"},[63]={"Rain","rain"},[65]={"Heavy rain","heavy-rain"},
 [66]={"Freezing rain","sleet"},[67]={"Freezing rain","sleet"},
 [71]={"Light snow","snow"},[73]={"Snow","snow"},[75]={"Heavy snow","snow"},
 [77]={"Snow grains","snow"},[80]={"Showers","rain"},[81]={"Showers","rain"},
 [82]={"Heavy showers","heavy-rain"},[85]={"Snow showers","snow"},[86]={"Snow showers","snow"},
 [95]={"Thunderstorm","thunder"},[96]={"Thunderstorm","thunder"},[99]={"Thunderstorm","thunder"},
}
function M.number(x)
    local n = tonumber(x)
    if n and n == n and n ~= math.huge and n ~= -math.huge then return n end
end
function M.round(x)
    local n = M.number(x)
    if not n then return nil end
    return n >= 0 and math.floor(n + .5) or math.ceil(n - .5)
end
function M.deg(x)
    local n = M.round(x)
    return n and tostring(n).."°" or "—"
end
function M.wmo(code, is_day)
    local e = codes[M.number(code)] or {"Weather","cloudy"}
    return e[1], (is_day == 0 and e[3]) or e[2]
end
-- Gregorian arithmetic independent of the Kindle's configured local timezone.
local function days(y,m,d)
    y = y - (m <= 2 and 1 or 0)
    local era = math.floor(y/400)
    local yy = y-era*400
    local mm = m + (m > 2 and -3 or 9)
    return era*146097 + yy*365 + math.floor(yy/4)-math.floor(yy/100)
        + math.floor((153*mm+2)/5)+d-1-719468
end
function M.utc(y,m,d,h,minute)
    return days(y,m,d)*86400+(h or 0)*3600+(minute or 0)*60
end
function M.offset(epoch)
    local y = tonumber(os.date("!%Y",epoch))
    local function lastSunday(month)
        return 31 - ((days(y,month,31)+4)%7)
    end
    -- Europe/Amsterdam: summer time starts/ends at 01:00 UTC.
    local start = M.utc(y,3,lastSunday(3),1)
    local finish = M.utc(y,10,lastSunday(10),1)
    return epoch >= start and epoch < finish and 7200 or 3600
end
function M.localDate(epoch)
    return os.date("!*t",epoch+M.offset(epoch))
end
function M.dateKey(epoch)
    return os.date("!%Y-%m-%d",epoch+M.offset(epoch))
end
function M.clock(epoch)
    epoch = M.number(epoch)
    return epoch and os.date("!%H:%M",epoch+M.offset(epoch)) or "—"
end
function M.nextDelay(now, interval)
    interval = M.number(interval) or 3600
    if interval <= 0 then return 0 end
    -- Avoid an alarm expiring while Wi-Fi is still connecting; at most a minute
    -- past a boundary, rather than drifting by a full hour at every refresh.
    return math.max(60, interval - now % interval)
end
function M.valid(data)
    if type(data)~="table" or type(data.current)~="table"
        or type(data.hourly)~="table" or type(data.daily)~="table" then return false end
    local t=M.number(data.current.temperature_2m)
    if not t or t < -100 or t > 80 then return false end
    if type(data.hourly.time)~="table" or type(data.daily.time)~="table"
        or #data.hourly.time == 0 or #data.daily.time == 0 then return false end
    for _,field in ipairs({"temperature_2m_max","temperature_2m_min","weather_code","sunrise","sunset"}) do
        if type(data.daily[field])~="table" then return false end
    end
    return M.number(data.hourly.time[1])~=nil and M.number(data.daily.time[1])~=nil
end
local function at(t,k,i)
    return type(t[k])=="table" and M.number(t[k][i]) or nil
end
function M.make(data,fetched,now,config)
    now=now or os.time()
    config=config or {city="Eindhoven"}
    local dt=M.localDate(now)
    local result={city=config.city,day=tostring(dt.day),month=months_upper[dt.month].." "..dt.year,
        weekday=weekdays[dt.wday],date_key=M.dateKey(now),rain={},future={},
        age=math.max(0,now-(M.number(fetched) or 0)),fetched=fetched}
    result.stale=result.age>90*60
    if not M.valid(data) then result.no_data=true; return result end
    local cur,hourly,daily=data.current,data.hourly,data.daily
    result.temperature=M.deg(cur.temperature_2m)
    result.feels=M.deg(cur.apparent_temperature)
    result.condition,result.icon=M.wmo(cur.weather_code,cur.is_day)
    local start
    for i,t in ipairs(hourly.time) do
        t=M.number(t)
        if t and t <= now and t+3600>now then start=i; break end
    end
    if start then
        for n=0,5 do
            local i=start+n
            local p=at(hourly,"precipitation_probability",i)
            if p and (p<0 or p>100) then p=nil end
            result.rain[n+1]={prob=p,label=n==0 and "Now" or "+"..n.."h",
                snowfall=at(hourly,"snowfall",i),time=at(hourly,"time",i)}
        end
    else
        for n=0,5 do result.rain[n+1]={label=n==0 and "Now" or "+"..n.."h"} end
    end
    local today
    for i,t in ipairs(daily.time) do
        if M.number(t) and M.dateKey(t)==result.date_key then today=i;break end
    end
    if today then
        result.high=M.deg(at(daily,"temperature_2m_max",today))
        result.low=M.deg(at(daily,"temperature_2m_min",today))
        result.sunrise=M.clock(at(daily,"sunrise",today))
        result.sunset=M.clock(at(daily,"sunset",today))
        for n=1,3 do
            local i=today+n
            if M.number(daily.time[i]) then
                local date=M.localDate(daily.time[i])
                local _,ico=M.wmo(at(daily,"weather_code",i),1)
                result.future[#result.future+1]={label=n==1 and "Tomorrow · "..weekdays[date.wday] or weekdays[date.wday],
                    high=M.deg(at(daily,"temperature_2m_max",i)),low=M.deg(at(daily,"temperature_2m_min",i)),icon=ico}
            end
        end
    end
    local wind=M.round(cur.wind_speed_10m)
    result.wind=wind and wind.." km/h" or "—"
    local gust=M.round(cur.wind_gusts_10m)
    local direction=M.number(cur.wind_direction_10m)
    local dirs={"N","NE","E","SE","S","SW","W","NW"}
    result.wind_detail=(direction and dirs[math.floor((direction%360)/45+.5)%8+1] or "—")
        .." · Gusts "..(gust and gust.." km/h" or "—")
    local known,maxp,first=0,0,nil
    for i,r in ipairs(result.rain) do
        if r.prob then
            known=known+1; maxp=math.max(maxp,r.prob)
            if r.prob>=60 and not first then first=i end
        end
    end
    if result.stale then
        result.summary="Connection unavailable; the displayed forecast is outdated."
    elseif M.number(cur.weather_code) and M.number(cur.weather_code)>=95 then
        result.summary="Thunderstorms are forecast."
    elseif gust and gust>=50 then
        result.summary="Strong wind gusts are forecast."
    elseif first then
        local p=M.round(result.rain[first].prob)
        result.summary=first==1 and "Rain chance is high this hour ("..p.."%)."
            or "Rain chance reaches "..p.."% in "..(first-1)..((first-1)==1 and " hour." or " hours.")
    elseif known==6 and maxp<30 then
        result.summary="Rain chance stays low over the next 6 hours."
    elseif known>0 then
        result.summary="Rain chance up to "..M.round(maxp).."% over the next hours."
    else
        result.summary="Hourly rain probabilities are currently unavailable."
    end
    return result
end
return M
