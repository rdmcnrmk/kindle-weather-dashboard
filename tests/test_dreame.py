"""Protocol contract tests. All cloud/robot replies are synthetic; no real cleaning."""
import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from lupa.lua51 import LuaRuntime
from test_weather import PLUGIN, lua_table


class DreameTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('package.path=' + json.dumps(str(PLUGIN / '?.lua')) + '..";"..package.path')
        self.lua.globals().encode = lambda t: json.dumps(self.native(t), sort_keys=True, separators=(',', ':'))
        self.lua.globals().decode = lambda s: lua_table(self.lua, json.loads(s))
        self.lua.globals().hash = lambda s: hashlib.md5(s.encode()).hexdigest()
        self.lua.globals().unb64 = lambda s: base64.b64decode(s).decode()
        self.lua.execute('''
            package.preload['json']=function()return {encode=encode,decode=decode}end
            package.preload['ffi/sha2']=function()return {md5=hash}end
            package.preload['mime']=function()return {unb64=unb64}end
        ''')
        self.calls = []
        self.responses = []
        self.saved = []
        self.config = lua_table(self.lua, dict(region='eu', username='test@example.invalid',
            access_token='fake-access', refresh_token='fake-refresh', expires_at=999999,
            did='fake-device', model='dreame.vacuum.r9445a', bind_domain='eu.test.invalid'))
        self.client = self.lua.eval('require("dreamehome")').new(
            self.config, self.request, lambda c: self.saved.append(self.native(c)) or True, lambda: 1000)
        self.client.id = 0

    def native(self, t):
        if not hasattr(t, 'items'):
            return t
        items = list(t.items())
        if items and all(isinstance(k, int) for k, _ in items):
            return [self.native(t[i]) for i in range(1, len(items) + 1)]
        return {k: self.native(v) for k, v in items}

    def request(self, url, headers, body):
        self.calls.append((url, self.native(headers), body))
        if not self.responses:
            raise AssertionError('Unexpected network request')
        status, data = self.responses.pop(0)
        return status, json.dumps(data) if data is not None else ''

    def reply(self, result):
        self.responses.append((200, dict(code=0, data=dict(result=result))))

    def idle(self):
        self.reply([dict(siid=4, piid=7, code=0, value=0)])

    def test_login_salts_password_and_saves_tokens_without_password(self):
        self.responses.append((200, dict(access_token='next', refresh_token='rotate', expires_in=3600)))
        self.assertTrue(self.client.login(self.client, 'a+b@example.invalid', 'a-secret'))
        url, headers, body = self.calls[0]
        self.assertEqual(url, 'https://eu.iot.dreame.tech:13267/dreame-auth/oauth/token')
        self.assertIn('a%2Bb%40example.invalid', body)
        self.assertIn(hashlib.md5(b'a-secretRAylYC%fmSKp7%Tq').hexdigest(), body)
        self.assertNotIn('a-secret', body)
        self.assertEqual(self.saved[-1]['refresh_token'], 'rotate')
        self.assertNotIn('password', self.saved[-1])

    def test_expired_token_refreshes_before_read(self):
        self.config.expires_at = 1000
        self.responses += [(200, dict(access_token='new', refresh_token='rotated', expires_in=3600)),
                           (200, dict(code=0, data=dict(page=dict(records=[]))))]
        self.client.devices(self.client)
        self.assertIn('grant_type=refresh_token', self.calls[0][2])
        self.assertEqual(self.calls[1][1]['dreame-auth'], 'new')
    def test_login_distinguishes_transport_auth_rate_limit_and_bad_protocol(self):
        factory=self.lua.eval('require("dreamehome")').new
        for reason,expected in [('tcp','TCP/DNS'),('tls_handshake','TLS handshake'),
                                ('tls_support','neither native hostname'),('timeout','timed out')]:
            c=factory(self.config,lambda *_,r=reason:(None,None,r))
            ok,error=c.login(c,'test@example.invalid','fake-secret')
            self.assertIsNone(ok)
            self.assertIn(expected,error)
            self.assertNotIn('fake-secret',error)
        for status,expected in [(401,'HTTP 401'),(429,'rate limit'),(503,'HTTP 503'),(200,'unexpected')]:
            self.responses.append((status,dict(password='never echo server secrets')))
            ok,error=self.client.login(self.client,'test@example.invalid','fake-secret')
            self.assertIsNone(ok)
            self.assertIn(expected,error)
            self.assertNotIn('never echo',error)

    def test_cloud_success_codes_are_separate_from_robot_result_codes(self):
        for cloud_code in [0,200]:
            self.responses.append((200,dict(code=cloud_code,success=True,
                data=dict(result=[dict(code=0,value=0)]))))
            state=self.client.rpc(self.client,'get_properties',lua_table(self.lua,[]))
            self.assertEqual(state[1].value,0)
        # A cloud success must never turn a robot rejection into acceptance.
        self.responses += [(200,dict(code=200,data=dict(result=[dict(code=0,value=0)]))),
                           (200,dict(code=200,data=dict(result=dict(code=-1))))]
        ok,error=self.client.clean(self.client,'all')
        self.assertIsNone(ok)
        self.assertIn('robot rejected',error)

    def test_cloud_errors_expose_only_status_and_numeric_service_code(self):
        for status,body,expected in [
            (403,dict(code=403,msg='private-secret'),'HTTP 403'),
            (200,dict(code=10001,msg='private-secret'),'service code 10001'),
            (200,dict(code=0,success=False,msg='private-secret'),'service code 0'),
            (200,dict(code='private-secret',msg='private-secret'),'service code unknown'),
            (200,dict(code=200),'no data')]:
            self.responses.append((status,body))
            result,error=self.client.api(self.client,'read-only')
            self.assertIsNone(result)
            self.assertIn(expected,error)
            self.assertNotIn('private-secret',error)

    def test_property_wire_matches_reference_correlation_keys_and_bounded_ids(self):
        # Reference: Tasshack device.py _request_properties and protocol.py send.
        # These expected objects are independent of the Lua request builder.
        factory=self.lua.eval('require("dreamehome")').new
        self.config.expires_at=2**40
        client=factory(self.config,self.request,None,lambda:1795340000)
        self.assertGreaterEqual(client.id,1)
        self.assertLessEqual(client.id,100)
        client.id=500000
        self.idle()
        self.assertEqual(client.taskStatus(client),0)
        self.reply([dict(code=0,value='[]')])
        client.shortcuts(client)
        for call,prop,request_id in zip(self.calls,[('11',7),('52',48)],[1,2]):
            wire=json.loads(call[2])
            self.assertEqual(wire['id'],request_id)
            self.assertEqual(wire['data'],dict(did='fake-device',id=request_id,
                method='get_properties',params=[dict(did=prop[0],siid=4,piid=prop[1])]))
            self.assertEqual(wire['did'],'fake-device')

    def test_80001_and_mismatched_task_status_cannot_start_cleaning(self):
        for reply in [dict(code=80001,success=False,data=None),
                      dict(code=0,data=dict(result=[dict(code=0,value=0,siid=4,piid=48)]))]:
            self.responses.append((200,reply))
            before=len(self.calls)
            ok,error=self.client.clean(self.client,'all')
            self.assertIsNone(ok)
            self.assertEqual(len(self.calls),before+1)
            self.assertEqual(json.loads(self.calls[-1][2])['data']['method'],'get_properties')

    def test_all_sends_one_custom_clean_action_with_signed_envelope(self):
        self.idle()
        self.reply(dict(code=0))
        self.assertTrue(self.client.clean(self.client, 'all'))
        url, _, body = self.calls[-1]
        self.assertTrue(url.endswith('/dreame-iot-com-eu/device/sendCommand'))
        sent = json.loads(body)
        self.assertEqual(sent['data']['params'], dict(did='fake-device', siid=4, aiid=1,
                                                     **{'in': [dict(piid=1, value=1)]}))
        # Independent reference for upstream's nested-object signature rules.
        splice = 'data=[did="fake-device"&id=2&method="action"&params=[aiid=1&did="fake-device"&siid=4]]&did=fake-device&id=2'
        expected = hashlib.md5((splice + '1000000' + 'EETjszu*XI5znHsI').encode()).hexdigest()
        self.assertEqual(sent['sign'], expected)

    def test_named_shortcuts_preserve_dreamehome_cleaning_settings(self):
        for target, shortcut_id in [('kitchen', 26), ('dining', 32)]:
            self.idle()
            shortcuts = [dict(id=shortcut_id, name=base64.b64encode(target.title().encode()).decode())]
            self.reply([dict(code=0, value=json.dumps(shortcuts))])
            self.reply(dict(code=0))
            self.assertTrue(self.client.clean(self.client, target))
            sent = json.loads(self.calls[-1][2])['data']['params']
            self.assertEqual(sent['in'], [dict(piid=1, value=25), dict(piid=10, value=str(shortcut_id))])

    def test_missing_duplicate_invalid_shortcuts_never_send_clean_action(self):
        name = base64.b64encode(b'Kitchen').decode()
        for shortcuts in [[], [dict(id=26, name=name), dict(id=27, name=name)], [dict(id=999, name=name)]]:
            before = len(self.calls)
            self.idle()
            self.reply([dict(code=0, value=json.dumps(shortcuts))])
            ok, _ = self.client.clean(self.client, 'kitchen')
            self.assertIsNone(ok)
            self.assertTrue(all(json.loads(c[2])['data']['method'] == 'get_properties' for c in self.calls[before:]))

    def test_timeout_never_retries_cleaning_action(self):
        self.idle()
        self.responses.append((None, None))
        ok, _ = self.client.clean(self.client, 'all')
        self.assertIsNone(ok)
        self.assertEqual(len(self.calls), 2)

    def test_busy_unknown_rejected_and_unauthorized_replies(self):
        for state in [dict(code=0, value=1), dict(code=-1), dict(code=0, value=8)]:
            self.reply([state])
            ok, _ = self.client.clean(self.client, 'all')
            self.assertIsNone(ok)
        self.idle()
        self.reply(dict(code=-1))
        self.assertIsNone(self.client.clean(self.client, 'all')[0])
        self.responses.append((401, dict(code=401)))
        self.assertIsNone(self.client.devices(self.client)[0])
        self.assertEqual(self.config.expires_at, 0)

    def test_bad_region_model_target_and_routing_fail_before_network(self):
        self.config.region = 'eu.evil.invalid'
        self.assertIsNone(self.client.devices(self.client)[0])
        self.config.region = 'eu'
        self.config.model = 'unknown'
        self.assertIsNone(self.client.clean(self.client, 'all')[0])
        self.config.model = 'dreame.vacuum.r9445a'
        self.config.bind_domain = 'invalid'
        self.assertIsNone(self.client.clean(self.client, 'all')[0])
        self.assertIsNone(self.client.clean(self.client, 'invalid')[0])
        self.assertEqual(self.calls, [])

    def test_l50_variants_share_the_same_command_mapping(self):
        module=self.lua.eval('require("dreamehome")')
        for suffix in ['r9445a','r9445d','r9445g']:
            self.config.model='dreame.vacuum.'+suffix
            self.assertTrue(module.supportedModel(self.config.model))
            self.idle();self.reply(dict(code=0))
            self.assertTrue(self.client.clean(self.client,'all'))
        self.assertFalse(module.supportedModel('dreame.vacuum.r9493a'))

    def test_discovery_distinguishes_empty_unsupported_and_missing_routing(self):
        module=self.lua.eval('require("dreamehome")')
        self.assertIn('no visible robots',module.discoveryMessage(lua_table(self.lua,[])))
        unsupported=lua_table(self.lua,[dict(model='dreame.vacuum.unknown',customName='private name',
            did='private id',masterName='private email',mac='private mac')])
        message=module.discoveryMessage(unsupported)
        self.assertIn('dreame.vacuum.unknown',message)
        self.assertNotIn('private',message)
        missing=lua_table(self.lua,[dict(model='dreame.vacuum.r9445d',did='private id')])
        self.assertIn('routing information is missing',module.discoveryMessage(missing))

    def test_store_drops_password_and_disconnect_removes_both_files(self):
        with tempfile.TemporaryDirectory() as directory:
            self.lua.globals().directory = directory
            self.lua.execute('''
                package.preload['datastorage']=function()return {getSettingsDir=function()return directory end}end
                package.preload['util']=function()return {makePath=function()end}end
            ''')
            store = self.lua.eval('require("dreame_store")')
            self.config.password = 'never-persist'
            self.assertTrue(store.save(self.config))
            path = Path(directory) / 'dreamehome-session.json'
            self.assertNotIn('never-persist', path.read_text())
            self.assertEqual(store.load().did, 'fake-device')
            path.with_suffix('.json.tmp').write_text('partial')
            self.assertTrue(store.clear())
            self.assertFalse(list(Path(directory).iterdir()))

    def test_hit_areas_scale_and_leave_gaps_and_weather_untouched(self):
        tabs = self.lua.eval('require("dashboard_tabs")')
        for scale in [1, .5, 2]:
            for index, y in enumerate([532, 764, 996], 1):
                x, y = tabs.point(536*scale, y*scale, 1072*scale, 1448*scale)
                self.assertEqual(tabs.hitVacuum(x, y), index)
            self.assertIsNone(tabs.hitVacuum(536, 650))
            self.assertIsNone(tabs.hitVacuum(63, 500))
        self.assertEqual(tabs.hitTab(200, 70), 'weather')
        self.assertEqual(tabs.hitTab(700, 70), 'vacuum')
        self.lua.execute("table.insert(require('dashboard_tabs').items,{id='future',label='Future'})")
        self.assertEqual(tabs.hitTab(950, 70), 'future')
        self.assertEqual(tabs.tabRect(3)[2], 944/3)

    def test_tab_switches_do_not_fetch_or_send_commands_and_buttons_are_page_scoped(self):
        self.lua.execute('''
            fetches=0;pressed={};connected=0;enabled=true
            local W={};function W:extend(t)return setmetatable(t,{__index=self})end
            function W:new(t)t=setmetatable(t or {},{__index=self});if t.init then t:init()end;return t end
            package.preload['ui/widget/widget']=function()return W end
            package.preload['ui/geometry']=function()return {new=function(_,t)return t end}end
            package.preload['ffi/blitbuffer']=function()return {Color8=function(n)return n end}end
            package.preload['device']=function()return {screen={getWidth=function()return 1072 end,
                getHeight=function()return 1448 end}}end
            for _,name in ipairs({'ui/font','ui/widget/textwidget','ui/widget/imagewidget','logger'})do
                package.preload[name]=function()return {}end
            end
            package.preload['fridge_source']=function()return {fetch=function()fetches=fetches+1 end}end
            repaints=0
            package.preload['ui/uimanager']=function()return {setDirty=function(_,widget,mode)
                -- Match KOReader semantics: a refresh with nil paints no window.
                if widget=='all' and mode=='full' then
                    repaints=repaints+1;visible_page=view.page
                end
            end}end
            package.preload['dreame_controls']=function()return {enabled=function()return enabled end,
                press=function(n)pressed[#pressed+1]=n end,connect=function()connected=connected+1 end}end
            view=require('display_week'):create({},true)
        ''')
        view = self.lua.globals().view
        self.assertFalse(view.onDashboardTap(view, 500, 532))
        view.onDashboardTap(view, 700, 70)
        self.assertEqual(view.page, 'vacuum')
        self.assertEqual(self.lua.globals().visible_page, 'vacuum')
        self.assertEqual(self.lua.globals().repaints, 1)
        self.assertEqual(len(self.lua.globals().pressed), 0)
        for y in [532, 764, 996]:
            view.onDashboardTap(view, 500, y)
        self.assertEqual(self.native(self.lua.globals().pressed), [1, 2, 3])
        self.lua.execute('enabled=false')
        view.onDashboardTap(view, 500, 532)
        view.onDashboardTap(view, 500, 1200)
        self.assertEqual(len(self.lua.globals().pressed), 3)
        self.assertEqual(self.lua.globals().connected, 1)
        view.onDashboardTap(view, 200, 70)
        self.assertEqual(view.page, 'weather')
        self.assertEqual(self.lua.globals().visible_page, 'weather')
        self.assertEqual(self.lua.globals().repaints, 2)
        self.assertEqual(self.lua.globals().fetches, 1)
        self.lua.execute("sleep_view=require('display_week'):create({})")
        sleep_view = self.lua.globals().sleep_view
        self.assertFalse(sleep_view.onDashboardTap(sleep_view, 700, 70))
        self.assertEqual(sleep_view.page, 'weather')
        self.assertEqual(self.lua.globals().repaints, 2)

    def test_transport_checks_peer_and_hostname_before_sending_credentials(self):
        self.lua.execute('''
            sent=0;closed=0;reset=0;checkhost_ok=true
            local sock={settimeout=function()return 1 end,connect=function()return 1 end,
                sni=function()end,dohandshake=function()return 1 end,
                close=function()closed=closed+1 end,
                getpeercertificate=function()
                    if legacy then return {extensions=function()return {
                        ['2.5.29.17']={dNSName={legacy_name}}}end}end
                    return {checkhost=function()return checkhost_ok end}end}
            package.preload['socketutil']=function()return {set_timeout=function()end,
                reset_timeout=function()reset=reset+1 end}end
            package.preload['socket']=function()return {tcp=function()return sock end}end
            package.preload['ssl']=function()return {wrap=function(s,options)
                assert(options.verify=='peer');assert(options.cafile:match('dreame%-ca.pem$'));return s end}end
            package.preload['ltn12']=function()return {source={string=function()end}}end
            package.preload['socket.http']=function()return {request=function(req)
                assert(req.redirect==false)
                local conn=req.create();conn:settimeout();conn:connect('eu.iot.dreame.tech',13267)
                sent=sent+1;req.sink('{}');return 1,200 end}end
        ''')
        transport = self.lua.eval('require("dreame_transport")')
        headers = lua_table(self.lua, {'dreame-auth': 'fake-token'})
        self.assertEqual(transport.request('https://eu.iot.dreame.tech:13267/path', headers, 'secret')[0], 200)
        self.lua.execute('checkhost_ok=false')
        self.assertIsNone(transport.request('https://eu.iot.dreame.tech:13267/path', headers, 'secret')[0])
        self.assertEqual(self.lua.globals().sent, 1)
        self.assertEqual(self.lua.globals().reset, 2)
        self.assertEqual(self.lua.globals().closed, 2)
        self.lua.execute("legacy=true;legacy_name='*.iot.dreame.tech'")
        self.assertEqual(transport.request('https://eu.iot.dreame.tech:13267/path', headers, 'secret')[0], 200)
        self.lua.execute("legacy_name='attacker.invalid'")
        result=transport.request('https://eu.iot.dreame.tech:13267/path', headers, 'secret')
        self.assertIsNone(result[0])
        self.assertEqual(result[2], 'tls_hostname')
        self.assertEqual(self.lua.globals().sent, 2)
        self.assertIsNone(transport.request('https://evil.invalid/path', headers, 'secret'))

    def test_transport_distinguishes_write_empty_reply_and_truncated_reply(self):
        # Use the transport fixture above, then exercise its actual socket wrapper.
        self.test_transport_checks_peer_and_hostname_before_sending_credentials()
        self.lua.execute("legacy=false;checkhost_ok=true")
        self.lua.execute("""
            package.loaded['socket.http'].request=function(req)
                local c=req.create();c:connect('eu.iot.dreame.tech',13267)
                c.sock.send=function()return nil,'closed',0 end
                c.sock.receive=function()return nil,'closed','' end
                if mode=='write' then c:send('private-token');return nil,'closed' end
                if mode=='partial' then
                    c.sock.receive=function()return nil,'closed','HTTP/1.1 200' end
                elseif mode=='timeout' then
                    c.sock.receive=function()return nil,'timeout','' end
                end
                c:receive(5);return nil,'closed'
            end
        """)
        transport=self.lua.eval('require("dreame_transport")')
        for mode,reason in [('write','http_send'),('empty','http_no_response'),
                            ('partial','http_incomplete'),('timeout','timeout_http_no_response')]:
            self.lua.globals().mode=mode
            result=transport.request('https://eu.iot.dreame.tech:13267/path',
                                     lua_table(self.lua,{}),'private-token')
            self.assertIsNone(result[0])
            self.assertEqual(result[2],reason)

    def test_transport_deadline_prevents_another_read_and_logs_no_secrets(self):
        self.test_transport_checks_peer_and_hostname_before_sending_credentials()
        self.lua.execute("""
            legacy=false;checkhost_ok=true;now=100;os.time=function()return now end
            logs={};reads=0
            package.preload['logger']=function()return {info=function(...)
                for _,v in ipairs({...})do logs[#logs+1]=tostring(v)end end}end
            package.preload['ui/network/manager']=function()return {isWifiOn=function()return true end}end
            package.loaded['socket.http'].request=function(req)
                local c=req.create();c:settimeout();c:connect('eu.iot.dreame.tech',13267)
                c.sock.receive=function()reads=reads+1;now=146;return 'HTTP/' end
                c:receive(5);c:receive('*l');return 1,200
            end
        """)
        transport=self.lua.eval('require("dreame_transport")')
        result=transport.request('https://eu.iot.dreame.tech:13267/private-path',
                                 lua_table(self.lua,{'authorization':'private-token'}),'private-password')
        self.assertEqual(result[2],'timeout_total')
        self.assertEqual(self.lua.globals().reads,1)
        logs=self.lua.eval("table.concat(logs,' ')")
        self.assertIn('timeout_total',logs)
        self.assertIn('wifi_before=on',logs)
        self.assertNotIn('private-',logs)

    def test_transport_preserves_tcp_and_tls_timeout_phases(self):
        self.test_transport_checks_peer_and_hostname_before_sending_credentials()
        self.lua.execute("legacy=false;checkhost_ok=true")
        transport=self.lua.eval('require("dreame_transport")')
        for phase in ['tcp','tls_handshake']:
            self.lua.globals().phase=phase
            self.lua.execute("""
                local s=require('socket').tcp()
                s.connect=function()if phase=='tcp' then return nil,'timeout' end;return 1 end
                s.dohandshake=function()return nil,'timeout' end
            """)
            result=transport.request('https://eu.iot.dreame.tech:13267/path',lua_table(self.lua,{}),'secret')
            self.assertEqual(result[2],'timeout_'+phase)
            self.assertEqual(self.lua.globals().sent,2)

    def test_legacy_tls_dns_san_exact_wildcard_and_malformed_names(self):
        verify=self.lua.eval('''function(names,host)
            local cert={extensions=function()return {['2.5.29.17']={dNSName=names}}end}
            local ok,err=require('dreame_tls').verify(cert,host);return ok,err
        end''')
        for name in ['eu.iot.dreame.tech','EU.IOT.DREAME.TECH','*.iot.dreame.tech']:
            self.assertTrue(verify(lua_table(self.lua,[name]),'eu.iot.dreame.tech')[0])
        for name in ['iot.dreame.tech','*.dreame.tech','e*.iot.dreame.tech',
                     '*.*.dreame.tech','*.tech','eu.iot.dreame.tech.attacker.invalid',
                     'eu.iot.dreame.tech\x00.attacker.invalid','eu..iot.dreame.tech',
                     '-eu.iot.dreame.tech','eu.iot.dreame.tech.','']:
            self.assertFalse(verify(lua_table(self.lua,[name]),'eu.iot.dreame.tech')[0],name)
        self.assertFalse(verify(lua_table(self.lua,['*.iot.dreame.tech']),'a.eu.iot.dreame.tech')[0])
        self.assertFalse(verify(lua_table(self.lua,[]),'eu.iot.dreame.tech')[0])
        self.lua.execute('''
            local H=require('dreame_tls')
            local cert={checkhost=function()return false end,
                extensions=function()error('must not fall back after native mismatch')end}
            native_rejected=not H.verify(cert,'eu.iot.dreame.tech')
            cert.checkhost=function()error('native failure')end
            native_error_rejected=not H.verify(cert,'eu.iot.dreame.tech')
            missing_rejected=not H.verify({subject=function()return 'eu.iot.dreame.tech'end},'eu.iot.dreame.tech')
        ''')
        self.assertTrue(self.lua.globals().native_rejected)
        self.assertTrue(self.lua.globals().native_error_rejected)
        self.assertTrue(self.lua.globals().missing_rejected)

    def test_network_timeout_cancels_late_callback_and_double_taps(self):
        self.lua.execute('''
            works=0
            package.preload['weather_utils']=function()return {safeGoOnlineToRun=function(_,good,bad,suppress,after)
                assert(after==false);online=good;offline=bad end}end
            package.preload['ui/widget/infomessage']=function()return {new=function(_,t)return t end}end
            package.preload['ui/uimanager']=function()return {show=function()end,close=function()end,
                forceRePaint=function()end,setDirty=function()end}end
            controls=require('dreame_controls')
            work=function()works=works+1 end
            controls.run(work);controls.run(work)
            offline();online();online()
        ''')
        self.assertEqual(self.lua.globals().works, 0)
        self.assertFalse(self.lua.globals().controls.busy)
        self.assertFalse(self.lua.eval('require("fridge_power").isInteracting()'))
        self.lua.execute('controls.run(work);controls.run(work);online();online();offline()')
        self.assertEqual(self.lua.globals().works, 1)
        self.assertFalse(self.lua.globals().controls.busy)

    def test_login_wizard_keeps_fields_visible_and_preserves_password_exactly(self):
        self.lua.execute('''
            shown={};repaints=0;attempts=0
            package.loaded['dreamehome']=nil
            package.preload['ui/uimanager']=function()return {show=function(_,dialog)
                shown[#shown+1]=dialog end,close=function()end,
                setDirty=function(_,which)if which=='all' then repaints=repaints+1 end end}end
            package.preload['ui/widget/inputdialog']=function()return {new=function(_,d)
                d.getInputText=function(self)return self.input end
                d.onShowKeyboard=function(self)self.keyboard_shown=true end
                return d end}end
            package.preload['ui/widget/buttondialog']=function()return {new=function(_,d)return d end}end
            package.preload['ui/font']=function()return {getFace=function()return {}end}end
            package.preload['dreame_store']=function()return {load=function()return {}end,save=function()end}end
            package.preload['dreame_transport']=function()return {request=function()error('no network')end}end
            package.preload['dreamehome']=function()return {new=function(config)
                selected_region=config.region
                return {login=function(_,email,password)
                    attempts=attempts+1;entered_email=email;entered_password=password
                    return nil,'Synthetic login result' end}end}end
            package.preload['ui/widget/infomessage']=function()return {new=function(_,d)return d end}end
            controls=require('dreame_controls');controls.run=function(fn)fn()end
            controls.connect()
        ''')
        g = self.lua.globals()
        email = g.shown[len(g.shown)]
        self.assertIn('Email address', email.title)
        self.assertTrue(email.fullscreen and email.keyboard_shown)
        self.assertTrue(email.modal)
        self.assertEqual(email.input_hint, 'you@example.com')
        email.input = '  user@example.invalid  '
        email.buttons[1][2].callback()  # Region chooser retains entered email.
        chooser = g.shown[len(g.shown)]
        chooser.buttons[2][1].callback()  # US
        email = g.shown[len(g.shown)]
        self.assertEqual(email.buttons[1][2].text, 'Region: US')
        self.assertEqual(email.input, '  user@example.invalid  ')
        email.buttons[1][3].callback()
        password = g.shown[len(g.shown)]
        self.assertIn('Password', password.title)
        self.assertIn('user@example.invalid', password.title)
        self.assertEqual(password.text_type, 'password')  # KOReader provides Show password.
        self.assertTrue(password.fullscreen and password.keyboard_shown)
        self.assertTrue(password.modal)
        self.assertEqual(g.attempts, 0)
        password.input = 'discard-on-back'
        password.buttons[1][2].callback()
        email = g.shown[len(g.shown)]
        email.buttons[1][3].callback()
        password = g.shown[len(g.shown)]
        self.assertEqual(password.input, '')
        password.input = '  exact password + spaces  '
        password.buttons[1][3].callback()
        self.assertEqual(g.entered_email, 'user@example.invalid')
        self.assertEqual(g.entered_password, '  exact password + spaces  ')
        self.assertEqual(g.selected_region, 'us')
        self.assertEqual(g.attempts, 1)
        self.assertGreaterEqual(g.repaints, 4)

    def test_selecting_discovered_robot_saves_session_without_callback_crash(self):
        self.config.expires_at=2**40
        self.config.did=None
        self.config.model=None
        self.config.bind_domain=None
        g=self.lua.globals()
        g.session=self.config
        g.py_request=self.request
        g.py_save=lambda c:self.saved.append(self.native(c)) or bool(g.allow_save)
        self.lua.execute('''
            shown={};flags={};allow_save=true;repaints=0
            G_reader_settings={saveSetting=function(_,k,v)flags[k]=v end,flush=function()end}
            package.preload['dreame_store']=function()return {load=function()return session end,save=py_save}end
            package.preload['dreame_transport']=function()return {request=py_request}end
            package.preload['ui/widget/buttondialog']=function()return {new=function(_,d)return d end}end
            package.preload['ui/widget/infomessage']=function()return {new=function(_,d)return d end}end
            package.preload['ui/uimanager']=function()return {
                show=function(_,d)assert(d.modal);shown[#shown+1]=d end,
                close=function(_,d)d.closed=true end,
                setDirty=function(_,which)assert(which=='all');repaints=repaints+1 end}end
            controls=require('dreame_controls');controls.run=function(fn)fn()end
        ''')
        device=dict(model='dreame.vacuum.r9445g',did='chosen-robot',bindDomain='eu.iot.dreame.tech',customName='Kitchen robot')
        self.responses.append((200,dict(code=0,data=dict(page=dict(records=[device])))))
        g.controls.discover()
        picker=g.shown[len(g.shown)]
        self.assertEqual(picker.title,'Select your robot')
        picker.buttons[1][1].callback()
        self.assertEqual(self.saved[-1]['did'],'chosen-robot')
        self.assertEqual(self.saved[-1]['model'],'dreame.vacuum.r9445g')
        self.assertEqual(self.saved[-1]['bind_domain'],'eu.iot.dreame.tech')
        self.assertTrue(g.flags.dreame_controls_enabled)
        self.assertTrue(picker.closed)
        self.assertEqual(g.repaints,2)
        # Storage failure must leave selection open and controls disabled.
        self.lua.execute('allow_save=false;flags={}')
        self.responses.append((200,dict(code=0,data=dict(page=dict(records=[device])))))
        g.controls.discover()
        picker=g.shown[len(g.shown)]
        picker.buttons[1][1].callback()
        self.assertIsNone(picker.closed)
        self.assertIsNone(g.flags.dreame_controls_enabled)
        self.assertIn('Could not save',g.shown[len(g.shown)].text)

    def test_connection_check_reports_missing_shortcuts_without_cleaning(self):
        self.config.expires_at=2**40
        self.lua.globals().session=self.config
        self.lua.globals().py_request=self.request
        self.lua.execute('''
            package.preload['dreame_store']=function()return {load=function()return session end,save=function()return true end}end
            package.preload['dreame_transport']=function()return {request=py_request}end
            package.preload['ui/uimanager']=function()return {show=function(_,d)last_message=d.text end,
                setDirty=function()end}end
            package.preload['ui/widget/infomessage']=function()return {new=function(_,d)return d end}end
            controls=require('dreame_controls');controls.run=function(fn)fn()end
        ''')
        self.idle()
        self.reply([dict(code=0,value=json.dumps([dict(id=26,name=base64.b64encode(b'Kitchen').decode())]))])
        self.lua.globals().controls.check()
        text=self.lua.globals().last_message
        self.assertIn('Kitchen shortcut: found',text)
        self.assertIn('Dining shortcut: missing',text)
        self.assertEqual(len(self.calls),2)
        for call in self.calls:
            self.assertEqual(json.loads(call[2])['data']['method'],'get_properties')
        self.idle()
        self.responses.append((200,dict(code=80001,success=False,data=None)))
        self.lua.globals().controls.check()
        self.assertIn('Robot connection OK',self.lua.globals().last_message)
        self.assertIn('Shortcut lookup failed',self.lua.globals().last_message)
        lines=self.native(self.lua.globals().controls.statusLines())
        self.assertIn('connection OK', ' '.join(lines))


if __name__ == '__main__':
    unittest.main()
