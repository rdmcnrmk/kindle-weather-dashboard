import sys, json, unittest, tempfile, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from lupa.lua51 import LuaRuntime
ROOT=Path(__file__).resolve().parents[1]
PLUGIN=ROOT/'payload/koreader/plugins/weatherlockscreen.koplugin'
ZONE=ZoneInfo('Europe/Amsterdam')
def stamp(y,m,d,h=0,minute=0):
    return int(datetime.datetime(y,m,d,h,minute,tzinfo=datetime.timezone.utc).timestamp())
def fixture(now=None):
    now=now or stamp(2026,11,21,12)
    local=datetime.datetime.fromtimestamp(now,ZONE)
    midnight=local.replace(hour=0,minute=0,second=0,microsecond=0)
    dates=[int((midnight+datetime.timedelta(days=n)).timestamp()) for n in range(5)]
    hours=[now-now%3600+n*3600 for n in range(120)]
    return {'current':{'time':now,'temperature_2m':8.1,'apparent_temperature':5.3,'weather_code':3,
        'wind_speed_10m':14,'wind_direction_10m':225,'wind_gusts_10m':24,'is_day':1},
        'hourly':{'time':hours,'precipitation_probability':[30,45,65,30,10,10]+[10]*114,'snowfall':[0]*120},
        'daily':{'time':dates,'temperature_2m_max':[9,9,10,7,8],'temperature_2m_min':[3,4,5,3,2],
            'weather_code':[3,61,2,3,0],'sunrise':[v+8*3600+6*60 for v in dates],
            'sunset':[v+16*3600+42*60 for v in dates]}}
def lua_table(lua,obj):
    if isinstance(obj,dict): return lua.table_from({k:lua_table(lua,v) for k,v in obj.items()})
    if isinstance(obj,list): return lua.table_from([lua_table(lua,v) for v in obj])
    return obj
class WeatherTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('package.path='+json.dumps(str(PLUGIN/'?.lua'))+'..";"..package.path')
        self.model=self.lua.eval('require("fridge_model")')
        self.config=self.lua.table_from({'city':'Eindhoven'})
        self.now=stamp(2026,11,21,12)
    def render(self,data=None,now=None,fetched=None):
        now=self.now if now is None else now
        return self.model.make(lua_table(self.lua,fixture() if data is None else data),now if fetched is None else fetched,now,self.config)
    def test_all_lua_files_compile_as_lua51(self):
        compile=self.lua.eval('function(s) local f,e=loadstring(s); return f~=nil,e end')
        for p in (ROOT/'payload/koreader').rglob('*.lua'):
            ok,error=compile(p.read_text())
            self.assertTrue(ok,f'{p.name}: {error}')
    def test_approved_layout_data(self):
        v=self.render()
        self.assertEqual((v.day,v.month,v.weekday),('21','NOVEMBER 2026','Saturday'))
        self.assertEqual((v.temperature,v.feels,v.high,v.low),('8°','5°','9°','3°'))
        self.assertEqual(v.rain[3].prob,65)
        self.assertEqual(v.future[1].label,'Tomorrow · Sunday')
        self.assertIn('65% in 2 hours',v.summary)
        self.assertEqual((v.sunrise,v.sunset),('08:06','16:42'))
    def test_midnight_advances_today_and_tomorrow_even_offline(self):
        after=stamp(2026,11,21,23,1) # 00:01 on 22 November in Eindhoven
        v=self.render(now=after,fetched=self.now)
        self.assertEqual((v.day,v.weekday,v.high,v.low),('22','Sunday','9°','4°'))
        self.assertEqual(v.future[1].label,'Tomorrow · Monday')
        self.assertTrue(v.stale)
    def test_dst_matches_iana_timezone_database(self):
        for day in [datetime.datetime(2026,3,29,tzinfo=datetime.timezone.utc),datetime.datetime(2026,10,25,tzinfo=datetime.timezone.utc)]:
            for n in range(-48,49):
                t=int((day+datetime.timedelta(hours=n/2)).timestamp())
                expected=int(datetime.datetime.fromtimestamp(t,ZONE).utcoffset().total_seconds())
                self.assertEqual(self.model.offset(t),expected)
                self.assertEqual(self.model.dateKey(t),datetime.datetime.fromtimestamp(t,ZONE).strftime('%Y-%m-%d'))
    def test_missing_rain_is_not_reported_as_dry(self):
        f=fixture();f['hourly']['precipitation_probability']=[]
        v=self.render(f)
        self.assertIsNone(v.rain[1].prob)
        self.assertIn('unavailable',v.summary)
    def test_past_forecast_is_not_relabelled_now(self):
        f=fixture();f['hourly']['time']=[self.now-10000]
        v=self.render(f)
        self.assertIsNone(v.rain[1].prob)
    def test_invalid_and_nonfinite_readings(self):
        for temp in [None,float('nan'),float('inf'),-150,100]:
            f=fixture();f['current']['temperature_2m']=temp
            self.assertFalse(self.model.valid(lua_table(self.lua,f)))
        self.assertEqual(self.model.deg(None),'—')
        self.assertEqual(self.model.deg(-2.5),'-3°')
    def test_stale_is_visible_and_overrides_outdoor_advice(self):
        v=self.render(fetched=self.now-7200)
        self.assertTrue(v.stale);self.assertIn('outdated',v.summary)
    def test_hour_boundary_does_not_drift(self):
        self.assertEqual(self.model.nextDelay(self.now+17*60,3600),43*60)
        self.assertEqual(self.model.nextDelay(self.now+3590,3600),60)
        self.assertEqual(self.model.nextDelay(self.now,3600),3600)
    def test_risk_summary_does_not_recommend_unsafe_cycling(self):
        f=fixture();f['current']['wind_gusts_10m']=60
        self.assertIn('wind gusts',self.render(f).summary)
        f['current']['weather_code']=95
        self.assertIn('Thunderstorm',self.render(f).summary)
    def test_no_credentials_or_foreign_weather_provider_fallback(self):
        main=(PLUGIN/'main.lua').read_text()
        begin=main.index('function WeatherLockscreen:createWeatherWidget()')
        end=main.index('-- Choose the refresh mechanism',begin)
        self.assertNotIn('WeatherAPI:',main[begin:end])
        self.assertIn('default_api_key = ""',main)
        self.assertNotIn('%%2F',(PLUGIN/'fridge_source.lua').read_text())
if __name__=='__main__': unittest.main(verbosity=2)
