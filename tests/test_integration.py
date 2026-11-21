import sys,json,unittest,tempfile,shutil,importlib.util
from pathlib import Path
from test_weather import ROOT,PLUGIN,lua_table,fixture,stamp
from lupa.lua51 import LuaRuntime

def from_lua(obj):
    if hasattr(obj,'items'):
        items=dict(obj.items())
        if items and all(isinstance(k,int) for k in items):return [from_lua(items[i]) for i in range(1,len(items)+1)]
        return {k:from_lua(v) for k,v in items.items()}
    return obj

class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        g=self.lua.globals();g.CACHE_DIR=self.tmp.name;g.NOW=stamp(2026,11,21,12)
        g.decode_json=lambda s:lua_table(self.lua,json.loads(s))
        g.encode_json=lambda t:json.dumps(from_lua(t))
        g.mkdir_path=lambda p:Path(p).mkdir(parents=True,exist_ok=True)
        self.lua.execute('package.path='+json.dumps(str(PLUGIN/'?.lua'))+'..";"..package.path')
        self.lua.execute('''
            os.time=function()return NOW end
            package.preload['datastorage']=function()return {getDataDir=function()return CACHE_DIR end}end
            package.preload['logger']=function()return {warn=function()end,info=function()end}end
            package.preload['json']=function()return {decode=function(s)return decode_json(s)end,encode=function(t)return encode_json(t)end}end
            package.preload['util']=function()return {makePath=function(p)mkdir_path(p)end}end
            Source=require('fridge_source'); calls=0; response=nil
            Source.httpGet=function(url)calls=calls+1;return response end
        ''')
        self.source=g.Source
        self.plugin=self.lua.table_from({'refresh':True})
    def test_success_cache_first_no_extra_network_and_forced_refresh(self):
        g=self.lua.globals();g.response=json.dumps(fixture())
        d,f=self.source.fetch(self.plugin)
        self.assertEqual(g.calls,1);self.assertFalse(self.plugin.refresh)
        self.assertEqual(d.current.temperature_2m,8.1)
        self.plugin.prefer_cache=True;self.plugin.refresh=True
        self.source.fetch(self.plugin)
        self.assertEqual(g.calls,1);self.assertTrue(self.plugin.refresh)
        self.plugin.prefer_cache=False
        self.source.fetch(self.plugin)
        self.assertEqual(g.calls,2);self.assertFalse(self.plugin.refresh)
    def test_failure_preserves_cache_and_pending_retry(self):
        g=self.lua.globals();g.response=json.dumps(fixture());self.source.fetch(self.plugin)
        g.NOW=g.NOW+7200;g.response='not json';self.plugin.refresh=True
        d,f=self.source.fetch(self.plugin)
        self.assertIsNotNone(d);self.assertTrue(self.plugin.refresh)
        self.assertEqual(f,stamp(2026,11,21,12))
    def test_expired_cache_not_claimed_current(self):
        g=self.lua.globals();g.response=json.dumps(fixture());self.source.fetch(self.plugin)
        g.NOW=g.NOW+49*3600;g.response=None;self.plugin.refresh=True
        d,f=self.source.fetch(self.plugin)
        self.assertIsNone(d);self.assertIsNone(f)
    def test_api_url_has_no_key_and_uses_epoch_dates(self):
        url=self.source.url()
        self.assertIn('timezone=Europe%2FAmsterdam',url)
        self.assertIn('timeformat=unixtime',url)
        self.assertNotIn('apikey',url);self.assertNotIn('%%',url)

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        base=Path(self.tmp.name);self.app=base/'app';self.app.mkdir();self.target=base/'Kindle';self.target.mkdir()
        shutil.copytree(ROOT/'payload',self.app/'payload')
        shutil.copyfile(ROOT/'manifest.json',self.app/'manifest.json')
        (self.target/'system').mkdir();(self.target/'system/version.txt').write_text('Kindle 5.16.2.1.1 (409747 002)\n')
        (self.target/'documents').mkdir();(self.target/'documents/JAILBROKEN.txt').write_text('You are jailbroken!')
        (self.target/'documents/book.epub').write_bytes(b'user book')
        (self.target/'koreader').mkdir();(self.target/'koreader/koreader.sh').write_text('# user runtime')
        spec=importlib.util.spec_from_file_location('installer',ROOT/'install.py');self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.module.ROOT=self.app
    def test_install_verify_and_rollback_preserve_books_runtime_previous_plugin(self):
        main=self.target/'koreader/plugins/weatherlockscreen.koplugin/main.lua';main.parent.mkdir(parents=True);main.write_text('-- old plugin')
        record=self.module.install(self.target)
        self.assertEqual((self.target/'documents/book.epub').read_bytes(),b'user book')
        self.assertEqual((self.target/'koreader/koreader.sh').read_text(),'# user runtime')
        self.assertIn('Weather Dashboard',main.read_text());self.assertFalse(record['runtime_added'])
        self.module.rollback(self.target)
        self.assertEqual(main.read_text(),'-- old plugin')
        self.assertFalse((self.target/'documents/Weather-Dashboard.sh').exists())
        self.assertEqual((self.target/'documents/book.epub').read_bytes(),b'user book')
    def test_update_checks_old_files_and_rollback_restores_previous_version(self):
        first=self.module.install(self.target)
        prior=(self.target/'documents/Weather-Dashboard.sh').read_bytes()
        changed=self.app/'payload/documents/Weather-Dashboard.sh'
        changed.write_bytes(prior+b"\n# update\n")
        manifest=json.loads((self.app/'manifest.json').read_text())
        manifest['payload']['documents/Weather-Dashboard.sh']=self.module.digest(changed)
        (self.app/'manifest.json').write_text(json.dumps(manifest))
        updated=self.module.install(self.target,update=True)
        self.assertIn('previous_record',updated)
        self.assertNotEqual((self.target/'documents/Weather-Dashboard.sh').read_bytes(),prior)
        self.module.rollback(self.target)
        self.assertEqual((self.target/'documents/Weather-Dashboard.sh').read_bytes(),prior)
        self.assertTrue((self.target/'hava-panosu-installation.json').exists())
    def test_wrong_device_rejected(self):
        (self.target/'system/version.txt').write_text('wrong firmware')
        with self.assertRaises(ValueError):self.module.install(self.target)
        self.assertFalse((self.target/'documents/Weather-Dashboard.sh').exists())
    def test_modified_package_rejected_before_writing(self):
        (self.app/'payload/documents/Weather-Dashboard.sh').write_text('modified')
        with self.assertRaises(ValueError):self.module.install(self.target)
        self.assertFalse((self.target/'documents/Weather-Dashboard.sh').exists())
    def test_symlink_escape_rejected_before_writing(self):
        outside=Path(self.tmp.name)/'outside';outside.mkdir()
        (self.target/'koreader/plugins').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):self.module.install(self.target)
        self.assertEqual(list(outside.iterdir()),[])
    def test_rollback_preserves_later_user_edits(self):
        self.module.install(self.target)
        p=self.target/'documents/Weather-Dashboard.sh';p.write_text('user changed this')
        with self.assertRaises(ValueError):self.module.rollback(self.target)
        self.assertEqual(p.read_text(),'user changed this')
    def test_unknown_filler_not_deleted(self):
        f=self.target/'fill_disk';f.mkdir();(f/'my-photo.jpg').write_bytes(b'photo')
        self.module.install(self.target)
        self.assertEqual((f/'my-photo.jpg').read_bytes(),b'photo')
    def test_english_launchers_replace_legacy_entries_and_rollback_restores_them(self):
        legacy=self.target/'documents/Hava-Panosu.sh'
        legacy.write_bytes(b'#!/bin/sh\n# old Turkish launcher\n')
        self.module.install(self.target)
        self.assertFalse(legacy.exists())
        self.assertTrue((self.target/'documents/Weather-Dashboard.sh').exists())
        self.module.rollback(self.target)
        self.assertEqual(legacy.read_bytes(),b'#!/bin/sh\n# old Turkish launcher\n')
        self.assertFalse((self.target/'documents/Weather-Dashboard.sh').exists())
if __name__=='__main__':unittest.main(verbosity=2)
