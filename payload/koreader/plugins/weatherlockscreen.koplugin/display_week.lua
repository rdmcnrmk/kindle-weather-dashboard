-- Weather Dashboard: approved portrait layout. AGPL-3.0-or-later.
-- Integrates with WeatherLockscreen / Kindle Weather Station's active sleep.
local BB=require('ffi/blitbuffer')
local Device=require('device')
local Font=require('ui/font')
local Geom=require('ui/geometry')
local TextWidget=require('ui/widget/textwidget')
local ImageWidget=require('ui/widget/imagewidget')
local Widget=require('ui/widget/widget')
local Model=require('fridge_model')
local Source=require('fridge_source')
local Config=require('fridge_config')
local logger=require('logger')
local Screen=Device.screen
local ROOT=(debug.getinfo(1,'S').source:match('^@(.*/)')) or 'plugins/weatherlockscreen.koplugin/'
local C={ink=BB.COLOR_BLACK,muted=BB.Color8(0x55),line=BB.Color8(0x99),light=BB.Color8(0xEE),white=BB.COLOR_WHITE}
local faces={}
local function face(px,bold)
    local key=tostring(px)..tostring(bold)
    if not faces[key] then
        local native_scale=Screen:scaleBySize(1000)/1000
        faces[key]=Font:getFace('inter/Inter-'..(bold and 'SemiBold' or 'Regular')..'.ttf',px/native_scale)
    end
    return faces[key]
end
local function size(str,px,bold)
    local w=TextWidget:new{text=str,face=face(px,bold),padding=0}
    local s=w:getSize();w:free();return s.w,s.h
end
local View=Widget:extend{}
function View:init()
    self.dimen=Geom:new{x=0,y=0,w=Screen:getWidth(),h=Screen:getHeight()}
end
function View:getSize() return self.dimen end
function View:_paint(bb,x0,y0)
    local scale=math.min(self.dimen.w/1072,self.dimen.h/1448)
    local xpad=x0+(self.dimen.w-1072*scale)/2
    local ypad=y0+(self.dimen.h-1448*scale)/2
    local function X(v) return math.floor(xpad+v*scale+.5) end
    local function Y(v) return math.floor(ypad+v*scale+.5) end
    local function P(v) return math.max(1,math.floor(v*scale+.5)) end
    local function rect(x,y,w,h,c) bb:paintRect(X(x),Y(y),P(w),P(h),c or C.ink) end
    local function text(x,y,str,px,bold,color,align,maxwidth)
        str=tostring(str or '—')
        local fs=P(px)
        while maxwidth and fs>P(13) and size(str,fs,bold)>maxwidth*scale do fs=fs-1 end
        local w=TextWidget:new{text=str,face=face(fs,bold),fgcolor=color or C.ink,padding=0}
        local box=w:getSize();local dx=X(x)
        if align=='right' then dx=dx-box.w elseif align=='center' then dx=dx-box.w/2 end
        w:paintTo(bb,math.floor(dx),Y(y));w:free()
    end
    local function rule(y) rect(64,y,944,1,C.line) end
    local function icon(name,x,y,w)
        local iw=ImageWidget:new{file=ROOT..'icons/week/'..(name or 'cloudy')..'.svg',width=P(w),height=P(w),alpha=true,original_in_nightmode=false}
        iw:getSize();iw:paintTo(bb,X(x),Y(y));iw:free()
    end
    local v=Model.make(self.data,self.fetched,os.time(),Config)
    bb:paintRect(x0,y0,self.dimen.w,self.dimen.h,C.white)
    text(64,48,v.city,21,true)
    text(1008,50,'HOME WEATHER',16,false,C.muted,'right')
    text(60,86,v.day,112,true)
    text(224,105,v.month,34,true,nil,nil,780)
    text(225,154,v.weekday,31)
    rect(64,218,944,2)
    if v.no_data then
        icon('cloudy',412,330,248)
        text(536,638,'Forecast not available yet',36,true,nil,'center',930)
        text(536,711,'Check the Wi-Fi connection.',26,false,C.muted,'center')
        text(536,759,'Wake with the power button, then refresh from the Weather Dashboard menu.',22,false,C.muted,'center',930)
        text(536,834,'A new attempt will be made automatically.',24,false,C.muted,'center')
    else
        text(59,242,v.temperature,174,true,nil,nil,620)
        icon(v.icon,738,269,238)
        text(64,433,v.condition,43,false,nil,nil,944)
        text(65,499,'Feels like '..v.feels..'   ·   High '..(v.high or '—')..' / Low '..(v.low or '—'),25,false,C.muted,nil,944)
        rule(558)
        text(64,582,'Next 6 hours',29,true)
        text(1008,590,'RAIN CHANCE',16,false,C.muted,'right')
        for n,r in ipairs(v.rain) do
            local cx=135+(n-1)*160
            text(cx,635,r.prob and Model.round(r.prob)..'%' or '—',27,true,nil,'center')
            rect(cx-30,690,60,80,C.light)
            if r.prob then local height=math.max(2,r.prob*.8);rect(cx-30,770-height,60,height) end
            text(cx,782,r.label,21,false,C.muted,'center')
        end
        rule(839)
        text(64,862,'WIND',17,true,C.muted)
        text(64,897,v.wind,40,true,nil,nil,480)
        text(64,954,v.wind_detail,21,false,C.muted,nil,495)
        rect(585,873,1,116,C.line)
        text(636,862,'SUNSET',17,true,C.muted)
        text(636,897,v.sunset,40,true)
        text(636,954,'Sunrise '..(v.sunrise or '—'),21,false,C.muted)
        rule(1019)
        rect(64,1047,944,96,C.light)
        text(86,1060,'OUTLOOK',16,true,C.muted)
        text(86,1091,v.summary,25,false,nil,nil,900)
        for i,f in ipairs(v.future) do
            local left=64+(i-1)*320
            text(left,1174,f.label,23,true,nil,nil,285)
            icon(f.icon,left,1221,87)
            text(left+105,1234,f.high,43,true,nil,nil,98)
            text(left+205,1251,'/ '..f.low,26,false,C.muted,nil,93)
            if i<3 then rect(left+299,1180,1,149,C.line) end
        end
    end
    rule(1377)
    local status='Open-Meteo · Hourly forecast'
    if v.no_data then status='Waiting for a connection'
    elseif v.stale then status='OUTDATED · '..math.max(1,math.floor(v.age/3600))..'h since update' end
    text(64,1394,status,17,false,C.muted,nil,780)
    local ok,battery=pcall(function() return Device:getPowerDevice():getCapacity() end)
    if G_reader_settings:readSetting("fridge_rtc_supported") == false then
        text(64,1352,"Scheduled wake unavailable; refresh from the menu.",18,true,C.ink,nil,944)
    elseif ok and Model.number(battery) and battery < Config.minimum_battery then
        text(64,1352,"Low battery; charge the device to resume updates.",18,true,C.ink,nil,944)
    end
    if ok and Model.number(battery) then text(1008,1394,'Battery '..Model.round(battery)..'%',17,false,C.muted,'right') end
end
function View:paintTo(bb,x,y)
    self.dimen.x,self.dimen.y=x,y
    local ok,err=pcall(self._paint,self,bb,x,y)
    if not ok then logger.err('KindleWeather: draw failed',err);error(err) end
end
local Display={}
function Display:create(plugin)
    local data,fetched=Source.fetch(plugin)
    return View:new{data=data,fetched=fetched}
end
return Display
