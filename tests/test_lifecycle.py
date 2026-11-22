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
            now=1000;os.time=function()return now end
            io.popen=function()return nil end
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
        lua.execute('''
            for _,t in ipairs(tasks)do if t.delay==30 then watch=t.callback;break end end
            now=1020;watch();now=1299;watch()
        ''')
        self.assertTrue(lua.globals().wl.dashboard_mode_enabled)
        self.assertEqual(lua.globals().suspends,0)
        lua.execute('now=1300;watch()')
        self.assertFalse(lua.globals().wl.dashboard_mode_enabled)
        lua.execute('local copy={};for _,t in ipairs(tasks)do copy[#copy+1]=t end;for _,t in ipairs(copy)do if t.delay==2 then t.callback()end end')
        self.assertEqual(lua.globals().suspends,1)
    def test_login_protects_wifi_and_blocks_watchdog_sleep_then_releases(self):
        lua=self.run_start(True)
        lua.execute('''
            now=1000;os.time=function()return now end
            io.popen=function()return nil end
            local net=require('ui/network/manager');offs=0
            net.isWifiOn=function()return true end
            net.turnOffWifi=function()offs=offs+1 end
            require('fridge_power').holdInteraction(300)
            local pending={};for _,t in ipairs(tasks)do pending[#pending+1]=t end
            for _,t in ipairs(pending)do if t.delay==20 then t.callback() end end
            for _,t in ipairs(tasks)do if t.delay==30 then watch=t.callback;break end end
            for i=1,4 do watch() end
        ''')
        self.assertTrue(lua.globals().wl.dashboard_mode_enabled)
        self.assertEqual(lua.globals().offs,0)
        self.assertEqual(lua.globals().suspends,0)
        lua.execute('''
            require('fridge_power').releaseInteraction();now=1300;watch()
            local pending={};for _,t in ipairs(tasks)do pending[#pending+1]=t end
            for _,t in ipairs(pending)do if t.delay==2 then t.callback()end end
        ''')
        self.assertFalse(lua.globals().wl.dashboard_mode_enabled)
        self.assertGreater(lua.globals().suspends,0)
    def test_login_started_during_suspend_delay_cancels_pending_suspend(self):
        lua=self.run_start(True)
        lua.execute('''
            for _,t in ipairs(tasks)do if t.delay==30 then watch=t.callback;break end end
            now=1300;watch()
            require('fridge_power').holdInteraction(300)
            for _,t in ipairs(tasks)do if t.delay==2 then t.callback();break end end
        ''')
        self.assertEqual(lua.globals().suspends,0)
    def test_activity_restarts_idle_deadline_and_delayed_suspend_rechecks_it(self):
        lua=self.run_start(True)
        lua.execute('''
            for _,t in ipairs(tasks)do if t.delay==30 then watch=t.callback;break end end
            now=1290;require('fridge_power').noteActivity()
            now=1300;watch();now=1589;watch()
        ''')
        self.assertTrue(lua.globals().wl.dashboard_mode_enabled)
        lua.execute('now=1590;watch()')
        self.assertFalse(lua.globals().wl.dashboard_mode_enabled)
        lua.execute('''
            require('fridge_power').noteActivity()
            for _,t in ipairs(tasks)do if t.delay==2 then t.callback();break end end
        ''')
        self.assertEqual(lua.globals().suspends,0)
    def test_idle_expiry_still_never_suspends_without_rtc(self):
        lua=self.run_start(False)
        lua.execute('''
            now=9999;wl.dashboard_mode_enabled=true
            for _,t in ipairs(tasks)do if t.delay==30 then t.callback();break end end
        ''')
        self.assertEqual(lua.globals().suspends,0)
class ResumeTests(unittest.TestCase):
    def runtime(self):
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.execute('package.path='+json.dumps(str(PLUGIN/'?.lua'))+'..";"..package.path')
        lua.execute('''
            enabled=true;next_tasks={};timers={};starts=0;auto_suspends=0;screen_shows=0
            device={screen={},screen_saver_mode=false,isKobo=function()return false end}
            G_reader_settings={readSetting=function(_,k)
                if k=='screensaver_type' then return 'weather' end
                if k=='fridge_rtc_test_done' then return true end
            end,saveSetting=function()end,flush=function()end}
            package.preload['device']=function()return device end
            package.preload['logger']=function()return {dbg=function()end,info=function()end,warn=function()end}end
            package.preload['ui/uimanager']=function()return {
                nextTick=function(_,fn)next_tasks[#next_tasks+1]=fn end,
                scheduleIn=function(_,delay,fn)timers[#timers+1]=fn end,
                unschedule=function()end,close=function()end}end
            package.preload['ui/widget/container/widgetcontainer']=function()return {extend=function(_,t)return t end}end
            package.preload['weather_dashboard']=function()return {
                start=function(_,wl,cache_only)starts=starts+1;cached=cache_only;wl.dashboard_mode_enabled=true end,
                stop=function(_,wl)wl.dashboard_mode_enabled=false end,
                onResume=function(_,wl)wl.dashboard_mode_enabled=false;return true end,
                onSuspend=function()return false end}end
            package.preload['weather_utils']=function()return {
                resumeFrontlight=function()end,suspendFrontlight=function()end,
                toggleSuspend=function()auto_suspends=auto_suspends+1 end}end
            package.preload['fridge_control']=function()return {enabled=function()return enabled end}end
            package.preload['ui/screensaver']=function()return {show=function()
                screen_shows=screen_shows+1;wl.refresh=false;device.screen_saver_mode=true end}end
            for _,name in ipairs({'dispatcher','device/wakeupmgr','ffi/blitbuffer',
                'ui/widget/screensaverwidget','l10n/gettext','weather_api','weather_menu','display_helper'})do
                package.preload[name]=function()return {}end
            end
            function runNext()
                local pending=next_tasks;next_tasks={}
                for _,fn in ipairs(pending)do fn()end
            end
        ''')
        lua.globals().wl=lua.execute((PLUGIN/'main.lua').read_text())
        lua.execute('wl.exitChargingRefresh=function()end;wl.closeWeatherScreensaver=function()end')
        return lua
    def test_manual_wake_opens_cached_interactive_dashboard_on_next_tick(self):
        lua=self.runtime()
        lua.execute('wl.dashboard_page="vacuum";wl:onResume()')
        self.assertEqual(lua.globals().starts,0)
        lua.execute('runNext()')
        self.assertEqual(lua.globals().starts,1)
        self.assertTrue(lua.globals().cached)
        self.assertEqual(lua.globals().wl.dashboard_page,'vacuum')
        self.assertEqual(lua.globals().auto_suspends,0)
    def test_delayed_screensaver_cleanup_opens_dashboard_once(self):
        lua=self.runtime()
        lua.execute('device.screen_saver_mode=true;wl:onResume();runNext()')
        self.assertEqual(lua.globals().starts,0)
        lua.execute('device.screen_saver_mode=false;wl:onOutOfScreenSaver();wl:onOutOfScreenSaver();runNext()')
        self.assertEqual(lua.globals().starts,1)
    def test_rtc_wake_keeps_automatic_refresh_and_resuspend(self):
        lua=self.runtime()
        lua.execute('wl.simulated_wakeup=true;wl:onResume();wl:onOutOfScreenSaver();runNext()')
        self.assertEqual(lua.globals().starts,0)
        self.assertEqual(lua.globals().screen_shows,2)
        lua.execute('timers[1]()')
        self.assertEqual(lua.globals().auto_suspends,1)
    def test_disabled_panel_and_new_suspend_cancel_resume_open(self):
        lua=self.runtime()
        lua.execute('enabled=false;wl:onResume();runNext()')
        self.assertEqual(lua.globals().starts,0)
        lua.execute('enabled=true;wl:onResume();wl:onSuspend();runNext()')
        self.assertEqual(lua.globals().starts,0)

if __name__=='__main__':unittest.main(verbosity=2)
