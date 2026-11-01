import ast,base64,datetime,json,logging,unittest
from types import SimpleNamespace
from pathlib import Path
tree=ast.parse((Path(__file__).resolve().parents[1]/'custom_components/aula/client.py').read_text(encoding='utf-8'))
method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='get_token')
source=ast.unparse(method)
ns={'base64':base64,'datetime':datetime,'json':json,'pytz':SimpleNamespace(utc=datetime.timezone.utc),'_LOGGER':logging.getLogger('test')}
exec(compile(ast.parse(source),'get_token.py','exec'),ns)
def token(delta):
 payload=base64.urlsafe_b64encode(json.dumps({'exp':datetime.datetime.now(datetime.timezone.utc).timestamp()+delta}).encode()).decode().rstrip('=')
 return 'header.'+payload+'.signature'
class Session:
 def __init__(self,values): self.values=list(values); self.calls=0
 def get(self,*a,**kw):
  self.calls+=1
  return SimpleNamespace(json=lambda:{'data':self.values.pop(0)})
class Client:
 get_token=ns['get_token']
 def __init__(self,issued,renewed=None):
  self.tokens={}; self._session=Session(issued); self.renewed=renewed; self.refreshes=0; self.apiurl='https://example.invalid'; self.failed=False
 def _get_access_token_param(self): return ''
 def login(self,force_refresh=False):
  assert force_refresh
  self.refreshes+=1
  if self.failed: raise RuntimeError('refresh denied')
  self._session=Session(self.renewed)
class TestWidget(unittest.TestCase):
 def test_expired_issued_token_refreshes_once_and_returns_live_token(self):
  fresh=token(3600); c=Client([token(-100)],[fresh]); self.assertEqual(c.get_token('0128'),'Bearer '+fresh); self.assertEqual(c.refreshes,1)
 def test_live_cached_token_avoids_network(self):
  fresh=token(3600); c=Client([]); c.tokens['0128']=('Bearer '+fresh,datetime.datetime.now(datetime.timezone.utc)); self.assertEqual(c.get_token('0128'),'Bearer '+fresh); self.assertEqual(c._session.calls,0)
 def test_recent_but_expired_cache_is_not_reused(self):
  fresh=token(3600); c=Client([fresh]); c.tokens['0128']=('Bearer '+token(-100),datetime.datetime.now(datetime.timezone.utc)); self.assertEqual(c.get_token('0128'),'Bearer '+fresh)
 def test_second_expired_response_stops_without_loop(self):
  c=Client([token(-100)],[token(-100)]); self.assertIsNone(c.get_token('0128')); self.assertEqual(c.refreshes,1); self.assertNotIn('0128',c.tokens)
 def test_refresh_failure_preserves_previous_session(self):
  c=Client([token(-100)]); c.failed=True; previous=c._session
  with self.assertRaises(RuntimeError): c.get_token('0128')
  self.assertIs(c._session,previous); self.assertEqual(c.refreshes,1)
 def test_missing_widget_token_does_not_attempt_login(self):
  c=Client([None]); self.assertIsNone(c.get_token('0128')); self.assertEqual(c.refreshes,0)
if __name__ == '__main__': unittest.main(verbosity=2)
