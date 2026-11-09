import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
import terminal_handoff as terminal
class TerminalTests(unittest.TestCase):
 def test_iterm_only_inserts_without_newline(self):
  calls=[]
  with patch('terminal_handoff.available',return_value=[dict(id='iterm2')]):
   result=terminal.open_input('python3 /safe/helper.py','iterm2',lambda args,**kw:(calls.append((args,kw)) or SimpleNamespace(returncode=0)))
  self.assertEqual(result,'input');self.assertIn('newline false',calls[0][0][2]);self.assertEqual(calls[0][0][-1],'python3 /safe/helper.py');self.assertNotIn('do script',calls[0][0][2])
 def test_terminal_copies_and_opens_but_never_submits_command(self):
  calls=[]
  with patch('terminal_handoff.available',return_value=[dict(id='terminal')]):
   result=terminal.open_input('python3 /safe/helper.py','terminal',lambda args,**kw:(calls.append((args,kw)) or SimpleNamespace(returncode=0)))
  self.assertEqual(result,'clipboard');self.assertEqual(calls[0][1]['input'],'python3 /safe/helper.py');self.assertIn('do script ""',calls[1][0][-1]);self.assertNotIn('/safe/helper.py',' '.join(calls[1][0]))
 def test_default_is_explicit_persistent_and_app_whitelisted(self):
  with tempfile.TemporaryDirectory() as directory,patch.object(terminal.cfg,'DATA',Path(directory)),patch('terminal_handoff.available',return_value=[dict(id='terminal')]):
   self.assertEqual(terminal.settings(),'');terminal.save('terminal');self.assertEqual(terminal.settings(),'terminal')
   self.assertEqual((Path(directory)/'terminal-preferences.json').stat().st_mode&0o777,0o600)
   with self.assertRaises(ValueError):terminal.save('unknown')
   with self.assertRaises(ValueError):terminal.open_input('command\nrun','terminal',None)
if __name__=='__main__':unittest.main(verbosity=2)
