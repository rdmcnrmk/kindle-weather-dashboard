import json,unittest
from test_weather import PLUGIN,ROOT
from lupa.lua51 import LuaRuntime
PATCH=ROOT/'payload/koreader/patches/2-fridge-weather.lua'
class LifecycleTests(unittest.TestCase):
    def run_start(self,ready):
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.execute('package.path='+json.dumps(str(PLUGIN/'?.lua'))+'..";"..package.path')
        lua.globals().READY=ready
        lua.execute('''
            local settings={auto_suspend_timeout_seconds=60,fridge_rtc_reason="native_screensaver_handoff",
                fridge_saved_settings={auto_suspend_timeout_seconds={present=true,value=900}}}
            G_reader_settings={
                readSetting=function(_,k)return settings[k]end,
                saveSetting=function(_,k,v)settings[k]=v end,isTrue=function()return false end}
            events={};tasks={};suspends=0
            local power={isFrontlightOn=function()return false end,isCharging=function()return false end}
            device={screen={},getPowerDevice=function()return power end,readyToSuspend=function()end,wakeupFromSuspend=function()end}
            wl={dashboard_mode_enabled=false};if READY then wl.wakeup_mgr={}end
            package.loaded['apps/filemanager/filemanager']={instance={weatherlockscreen=wl}}
            package.preload['device']=function()return device end
            package.preload['logger']=function()return {info=function()end,warn=function()end,err=function()end}end
            package.preload['ui/event']=function()return {new=function(_,n)return {name=n}end}end
            package.preload['ui/uimanager']=function()return {
                scheduleIn=function(_,delay,callback)tasks[#tasks+1]={delay=delay,callback=callback}end,
                broadcastEvent=function(_,event)events[#events+1]=event.name;wl.dashboard_mode_enabled=not wl.dashboard_mode_enabled end,
                suspend=function()suspends=suspends+1 end,show=function()end,nextTick=function()end}end
            package.preload['ui/widget/infomessage']=function()return {new=function(_,v)return v end}end
            package.preload['ui/network/manager']=function()return {isOnline=function()return true end,isWifiOn=function()return false end}end
            package.preload['libs/libkoreader-lfs']=function()return {attributes=function()return nil end,dir=function()return function()return nil end end}end
            dofile=function(path)if path:match('fridge_control') then return {enabled=function()return true end,enter=function()end}end end
        ''')
        lua.execute(PATCH.read_text())
        lua.execute('for _,task in ipairs(tasks) do if task.delay==4 then task.callback();break end end')
        return lua
    def test_no_automatic_sleep_without_rtc(self):
        lua=self.run_start(False)
        self.assertEqual(lua.globals().suspends,0)
        self.assertEqual(lua.eval('G_reader_settings:readSetting("auto_suspend_timeout_seconds")'),900)
        self.assertFalse(lua.eval('wl.dashboard_mode_enabled'))
        self.assertFalse(lua.eval('(function() for _,t in ipairs(tasks)do if t.delay==20 then return true end end return false end)()'))
    def test_supported_device_shows_dashboard_before_sleep(self):
        lua=self.run_start(True)
        self.assertTrue(lua.globals().wl.dashboard_mode_enabled)
        lua.execute('for _,t in ipairs(tasks)do if t.delay==20 then t.callback();break end end')
        self.assertFalse(lua.globals().wl.dashboard_mode_enabled)
        lua.execute('local copy={};for _,t in ipairs(tasks)do copy[#copy+1]=t end;for _,t in ipairs(copy)do if t.delay==2 then t.callback()end end')
        self.assertEqual(lua.globals().suspends,1)
if __name__=='__main__':unittest.main(verbosity=2)
