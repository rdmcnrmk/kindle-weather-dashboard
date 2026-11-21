"""Render the actual Lua layout with Pillow/Resvg adapters for KOReader widgets.
This checks geometry/content; device FreeType metrics and refresh need a real Kindle.
"""
import sys, math, io, json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from lupa.lua51 import LuaRuntime
import resvg_py
from test_weather import fixture,lua_table,stamp,PLUGIN,ROOT

def render(data,fetched,now,output):
    lua=LuaRuntime(unpack_returned_tuples=True)
    image=Image.new('RGB',(1072,1448),'white');draw=ImageDraw.Draw(image)
    violations=[];fonts={}
    def font(face):
        key=(face['name'],round(face['size']))
        if key not in fonts:fonts[key]=ImageFont.truetype(str(ROOT/'payload/koreader/fonts'/key[0]),key[1])
        return fonts[key]
    def measure(text,face):
        f=font(face);box=f.getbbox(text)
        return math.ceil(f.getlength(text)),box[3]-box[1]
    def check(x,y,w,h,kind):
        if min(x,y)<-.5 or x+w>1073 or y+h>1449:violations.append((kind,x,y,w,h))
    def paint_text(text,face,color,x,y):
        w,h=measure(text,face);check(x,y,w,h,text)
        draw.text((round(x),round(y)),text,font=font(face),fill=(int(color),)*3,anchor='lt')
    def rect(x,y,w,h,color):
        check(x,y,w,h,'rect')
        draw.rectangle((round(x),round(y),round(x+w-1),round(y+h-1)),fill=(int(color),)*3)
    def icon(path,x,y,w,h):
        check(x,y,w,h,'icon')
        b=resvg_py.svg_to_bytes(svg_path=path,width=round(w),height=round(h))
        icon=Image.open(io.BytesIO(b)).convert('RGBA')
        image.paste(icon,(round(x),round(y)),icon)
    g=lua.globals();g.py_measure=measure;g.py_text=paint_text;g.py_rect=rect;g.py_icon=icon
    g.FIXTURE=lua_table(lua,data);g.FETCHED=fetched;g.NOW=now
    lua.execute('package.path='+json.dumps(str(PLUGIN/'?.lua'))+'..";"..package.path')
    lua.execute('''
        os.time=function() return NOW end
        G_reader_settings={readSetting=function(_,key) if key=="fridge_rtc_supported" then return true end end}
        package.preload['logger']=function() return {err=function(...) error('paint error') end} end
        package.preload['ffi/blitbuffer']=function() return {COLOR_BLACK=0,COLOR_WHITE=255,Color8=function(n)return n end} end
        local Screen={getWidth=function()return 1072 end,getHeight=function()return 1448 end,scaleBySize=function(_,n)return n end}
        package.preload['device']=function()return {screen=Screen,getPowerDevice=function()return {getCapacity=function()return 76 end} end}end
        package.preload['ui/font']=function()return {getFace=function(_,name,px)return {name=name,size=px}end}end
        package.preload['ui/geometry']=function()return {new=function(_,t)return t end}end
        package.preload['ui/widget/widget']=function()
            local W={};function W:extend(t) return setmetatable(t,{__index=self}) end
            function W:new(t) t=setmetatable(t or {},{__index=self});if t.init then t:init() end;return t end
            return W
        end
        package.preload['ui/widget/textwidget']=function()
            local T={}
            function T:new(t)
                function t:getSize()local w,h=py_measure(self.text,self.face);return {w=w,h=h}end
                function t:paintTo(_,x,y)py_text(self.text,self.face,self.fgcolor,x,y)end
                function t:free()end
                return t
            end
            return T
        end
        package.preload['ui/widget/imagewidget']=function()
            local I={}
            function I:new(t)
                function t:getSize()return {w=self.width,h=self.height}end
                function t:paintTo(_,x,y)py_icon(self.file,x,y,self.width,self.height)end
                function t:free()end
                return t
            end
            return I
        end
        package.preload['fridge_source']=function()return {fetch=function()return FIXTURE,FETCHED end}end
        local bb={paintRect=function(_,x,y,w,h,c)py_rect(x,y,w,h,c)end}
        require('display_week'):create({}):paintTo(bb,0,0)
    ''')
    if violations:raise AssertionError(violations)
    image.convert('L').point(lambda v:round(v/17)*17).save(output,optimize=True)
    return output

if __name__=='__main__':
    output=ROOT/'artifacts/preview.png'
    output.parent.mkdir(parents=True,exist_ok=True)
    render(fixture(),stamp(2026,11,21,12),stamp(2026,11,21,12),output)
    print(output)
