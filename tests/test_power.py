import unittest,json
from lupa.lua51 import LuaRuntime
from test_weather import PLUGIN
class PowerTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('package.path='+json.dumps(str(PLUGIN/'?.lua'))+'..";"..package.path')
        self.lua.execute("Power=require('fridge_power')")
    def probe(self,definition):
        return self.lua.execute(definition+'; return Power.prepare(device)')
    def test_existing_manager_reused(self):
        manager,reason=self.probe('device={wakeup_mgr={}}')
        self.assertIsNotNone(manager);self.assertEqual(reason,'ready')
    def test_native_screensaver_handoff_does_not_fake_support(self):
        manager,reason=self.probe('device={getPowerDevice=function()return {lipc_handle={}}end,supportsScreensaver=function()return false end}')
        self.assertIsNone(manager);self.assertEqual(reason,'native_screensaver_handoff')
    def test_missing_power_link_is_reported(self):
        manager,reason=self.probe('device={getPowerDevice=function()return {}end,supportsScreensaver=function()return true end}')
        self.assertIsNone(manager);self.assertEqual(reason,'power_lipc_unavailable')
    def test_initialization_can_retry_after_power_setup(self):
        manager,reason=self.probe('device={supportsScreensaver=function()return true end}; device.getPowerDevice=function()return {lipc_handle={},initWakeupMgr=function()device.wakeup_mgr={}end}end')
        self.assertIsNotNone(manager);self.assertEqual(reason,'ready_after_retry')
    def test_manual_mode_restores_reader_timeout(self):
        timeout=self.lua.execute('''local settings={value=nil,
            readSetting=function()return {auto_suspend_timeout_seconds={present=true,value=900}}end,
            saveSetting=function(self,k,v)self.value=v end};
            Power.restoreManualTimeout(settings);return settings.value''')
        self.assertEqual(timeout,900)
    def test_first_wake_is_a_short_device_test_then_hourly(self):
        first,normal=self.lua.execute('''local pending={readSetting=function()return false end};
            local done={readSetting=function()return true end};
            return Power.refreshDelay(100,3600,pending),Power.refreshDelay(100,3600,done)''')
        self.assertEqual(first,120);self.assertEqual(normal,3500)
    def test_interaction_lease_expires_and_releases_without_changing_rtc(self):
        self.lua.execute('now=1000;os.time=function()return now end;Power.holdInteraction(300)')
        self.assertTrue(self.lua.eval('Power.isInteracting()'))
        self.lua.execute('now=1300')
        self.assertFalse(self.lua.eval('Power.isInteracting()'))
        self.lua.execute('Power.holdInteraction(120);Power.releaseInteraction()')
        self.assertFalse(self.lua.eval('Power.isInteracting()'))
        self.assertEqual(self.lua.eval('Power.refreshDelay(1300,3600,{readSetting=function()return false end})'),120)
    def test_idle_deadline_is_independent_of_short_network_lease(self):
        self.lua.execute('now=1000;os.time=function()return now end;Power.noteActivity()')
        self.lua.execute('now=1100;Power.holdInteraction(120);Power.releaseInteraction()')
        self.assertFalse(self.lua.eval('Power.canAutoSleep()'))
        self.lua.execute('now=1299')
        self.assertFalse(self.lua.eval('Power.canAutoSleep()'))
        self.lua.execute('now=1300')
        self.assertTrue(self.lua.eval('Power.canAutoSleep()'))
        self.lua.execute('Power.holdInteraction(300);now=1301')
        self.assertFalse(self.lua.eval('Power.canAutoSleep()'))
if __name__=='__main__':unittest.main(verbosity=2)
