"""Native Git object integration fixture; no network or GitHub writes."""
import base64
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from mcp_server.tools.github.batch import push_multiple_files

pytestmark = pytest.mark.skipif(not shutil.which('git'), reason='Git CLI required')


class Response:
    def __init__(self, data): self.data=data
    def json(self): return self.data


class LocalGitTreesAPI:
    def __init__(self, root):
        self.repo = root / 'repo.git'
        self.index = root / 'index'
        self.calls=[]
        self.env=dict(os.environ, GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.invalid',
                      GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.invalid')
        subprocess.run(['git','init','--bare','-q',str(self.repo)],check=True)

    def git(self,*args, data=None, env=None):
        return subprocess.check_output(['git','--git-dir='+str(self.repo),*args],
                                       input=data,env=env or self.env)

    def entries(self, sha):
        result=[]
        for raw in self.git('ls-tree','-r','-t','-z',sha).split(b'\x00'):
            if not raw: continue
            attrs,path=raw.split(b'\t',1)
            mode,type_,entry_sha=attrs.decode().split()
            result.append(dict(path=path.decode(),mode=mode,type=type_,sha=entry_sha))
        return result

    def _request(self,method,url,**kwargs):
        self.calls.append((method,url,kwargs))
        payload=kwargs.get('json',{})
        if method=='GET' and '/git/ref/heads/' in url:
            return Response({'object':{'sha':self.git('rev-parse','refs/heads/main').decode().strip()}})
        if method=='GET' and '/git/commits/' in url:
            return Response({'tree':{'sha':self.git('show','-s','--format=%T',url.rsplit('/',1)[1]).decode().strip()}})
        if method=='GET' and '/git/trees/' in url:
            return Response({'tree':self.entries(url.rsplit('/',1)[1]),'truncated':False})
        if method=='POST' and url.endswith('/git/blobs'):
            assert payload['encoding']=='base64'
            return Response({'sha':self.git('hash-object','-w','--stdin',data=base64.b64decode(payload['content'])).decode().strip()})
        if method=='POST' and url.endswith('/git/trees'):
            env=dict(self.env,GIT_INDEX_FILE=str(self.index))
            self.git('read-tree',payload['base_tree'],env=env)
            for entry in payload['tree']:
                self.git('update-index','--add','--cacheinfo',entry['mode'],entry['sha'],entry['path'],env=env)
            return Response({'sha':self.git('write-tree',env=env).decode().strip()})
        if method=='POST' and url.endswith('/git/commits'):
            parents=[arg for parent in payload.get('parents',[]) for arg in ['-p',parent]]
            return Response({'sha':self.git('commit-tree',payload['tree'],*parents,
                                           data=payload['message'].encode()).decode().strip()})
        if method=='PATCH' and '/git/refs/heads/' in url:
            assert payload['force'] is False
            current=self.git('rev-parse','refs/heads/main').decode().strip()
            self.git('merge-base','--is-ancestor',current,payload['sha'])
            self.git('update-ref','refs/heads/main',payload['sha'],current)
            return Response({'object':{'sha':payload['sha']}})
        raise AssertionError((method,url,kwargs))


def test_native_git_modes_symlink_target_and_unchanged_entry(tmp_path):
    client=LocalGitTreesAPI(tmp_path)
    records=[]
    old_blobs={}
    for path,mode,text in [('run.sh','100755','old'),('link','120000','old-target'),
                           ('plain','100644','old'),('untouched','100755','keep')]:
        sha=client.git('hash-object','-w','--stdin',data=text.encode()).decode().strip()
        old_blobs[path]=sha
        records.append(f'{mode} blob {sha}\t{path}\n')
    tree=client.git('mktree',data=''.join(records).encode()).decode().strip()
    head=client.git('commit-tree',tree,data=b'initial').decode().strip()
    client.git('update-ref','refs/heads/main',head)
    result=push_multiple_files(client,owner='local',repo='fixture',branch='main',message='update',
        expected_head_sha=head,files=[{'path':'run.sh','content':'new'},
          {'path':'link','content':'../new-target'},{'path':'plain','content':'new'},
          {'path':'new.txt','content':'new'},{'path':'new-exec.sh','content':'new','mode':'100755'}])
    assert result.startswith('✅'),result
    new=client.git('rev-parse','refs/heads/main').decode().strip()
    entries={e['path']:e for e in client.entries(new)}
    assert {p:e['mode'] for p,e in entries.items()} == {
        'run.sh':'100755','link':'120000','plain':'100644','untouched':'100755',
        'new.txt':'100644','new-exec.sh':'100755'}
    assert entries['untouched']['sha']==old_blobs['untouched']
    assert client.git('cat-file','blob',entries['link']['sha'])==b'../new-target'
    assert client.git('rev-parse',new+'^').decode().strip()==head
    assert len([1 for m,u,k in client.calls if m=='GET' and '/git/trees/' in u])==1
