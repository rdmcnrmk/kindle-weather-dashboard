import os,subprocess,tempfile,unittest
from pathlib import Path
from test_weather import ROOT
RUNNER=ROOT/'payload/koreader/fridge-run.sh'
class LauncherTests(unittest.TestCase):
    def execute(self,modules='langpicker blankwindow ad_screensaver usb',fail_unload=False,reader_exit=0):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);root=base/'Kindle';(root/'koreader').mkdir(parents=True)
            binaries=base/'bin';binaries.mkdir();state=base/'state';state.write_text(modules)
            commands=base/'commands';commands.touch();during=base/'during'
            get=binaries/'lipc-get-prop';get.write_text('#!/bin/sh\ncat "$STATE"\n');get.chmod(0o755)
            setprop=binaries/'lipc-set-prop'
            setprop.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$COMMANDS"
if [ "$1" = -s ]; then shift; fi
if [ "$2" = unload ]; then
  [ "$FAIL_UNLOAD" = 1 ] && exit 1
  sed 's/ad_screensaver//g' "$STATE" > "$STATE.tmp"
  mv "$STATE.tmp" "$STATE"
else
  printf ' ad_screensaver' >> "$STATE"
fi
''');setprop.chmod(0o755)
            (root/'koreader/koreader.sh').write_text('#!/bin/sh\ncat "$STATE" > "$DURING"\nexit '+str(reader_exit)+'\n')
            env={**os.environ,'PATH':str(binaries)+':'+os.environ['PATH'],'HAVA_PANOSU_ROOT':str(root),
                'STATE':str(state),'COMMANDS':str(commands),'DURING':str(during),'FAIL_UNLOAD':str(int(fail_unload))}
            result=subprocess.run(['sh',str(RUNNER)],env=env,capture_output=True,text=True)
            return result,state.read_text(),commands.read_text(),during.read_text() if during.exists() else None
    def test_temporary_handoff_and_restoration(self):
        result,after,commands,during=self.execute()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertNotIn('ad_screensaver',during)
        self.assertIn('ad_screensaver',after)
        self.assertIn(' usb',during)
        self.assertEqual(commands.splitlines(),['-s com.lab126.blanket unload ad_screensaver','-s com.lab126.blanket load ad_screensaver'])
    def test_standard_device_needs_no_changes(self):
        result,after,commands,during=self.execute(modules='langpicker blankwindow screensaver usb')
        self.assertEqual(result.returncode,0)
        self.assertEqual(commands,'');self.assertEqual(after,during)
    def test_failed_handoff_does_not_start_reader(self):
        result,after,commands,during=self.execute(fail_unload=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIsNone(during);self.assertIn('ad_screensaver',after)
    def test_reader_failure_restores_original_module(self):
        result,after,commands,during=self.execute(reader_exit=42)
        self.assertEqual(result.returncode,42)
        self.assertIn('ad_screensaver',after)
if __name__=='__main__':unittest.main(verbosity=2)
