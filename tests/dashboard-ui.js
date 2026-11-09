'use strict';
// File previews must not include unrelated settings or credential reference registries.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../dashboard/app.js'),'utf8');
const context=vm.createContext({});
for(const [start,end] of [['function connectionFiles(','function renderConnectionAdvanced('],['function knownGitSshHost(','function reuseKeyPath(']])vm.runInContext(source.slice(source.indexOf(start),source.indexOf(end)),context);
const files={'connection-personal.gitconfig':'personal git','ssh-connection-personal.config':'personal ssh','connection-work.gitconfig':'unrelated git','profile-team.gitconfig':'shared git','ssh-team.config':'shared ssh','profiles.json':'all reference metadata','ssh.config':'# aliases\nHost home\n    User me\nHost office\n    User someone\nHost *\n'};
assert.deepEqual(Object.keys(context.connectionFiles(files,{id:'personal',kind:'git',profile:''})),['connection-personal.gitconfig','ssh-connection-personal.config']);
assert.deepEqual(Object.keys(context.connectionFiles(files,{id:'personal',kind:'git',profile:'team'})),['profile-team.gitconfig','ssh-team.config']);
const server=context.connectionFiles(files,{id:'home',kind:'server'});
assert.equal(Object.values(server)[0],'Host home\n    User me');
assert.deepEqual(Object.keys(context.connectionFiles(files,{id:'absent',kind:'server'})),[]);
for(const host of ['github.com','gitlab.com:2222','GITHUB.COM'])assert.equal(context.knownGitSshHost({kind:'git',host}),true);
for(const host of ['github.com.example.net','git.example.net','https://github.com','github.com/org/repo.git'])assert.equal(context.knownGitSshHost({kind:'git',host}),false);
assert.equal(context.knownGitSshHost({kind:'server',host:'github.com'}),false);
console.log('PASS: connection-only preview, explicit shared scope, SSH alias isolation, official Git host suggestions');

// Importing the same existing bws registration is idempotent and creates valid IDs.
const workflow=fs.readFileSync(require('node:path').join(__dirname,'../dashboard/secret-workflows.js'),'utf8');
vm.runInContext("const draft={credentials:[],connections:[]};",context);
for(const [code,start,end] of [[source,'function makeCredential(','function newCredential('],[source,'function secretPurpose(','function renderSecrets('],[workflow,'function flowReference(','function flowConnectionRecords(']])vm.runInContext(code.slice(code.indexOf(start),code.indexOf(end)),context);
vm.runInContext("const view='secrets';",context);
const first=context.flowReference({item:'Personal SSH 키',kind:'note'},'ssh-key');
assert.match(first.id,/^[a-z][a-z0-9-]{0,63}$/);
assert.equal(context.flowReference({item:'Personal SSH 키',kind:'note'},'ssh-key'),first);
assert.equal(vm.runInContext('draft.credentials.length',context),1);
console.log('PASS: bws import reuses existing references and accepts existing item names');

const center=fs.readFileSync(require('node:path').join(__dirname,'../dashboard/control-center.js'),'utf8');
vm.runInContext(center.slice(center.indexOf('function portableSettings('),center.indexOf('function renderControlCenter(')),context);
const original={credentials:[]},keys=[{item:'personal-key',kind:'note'}];
const exported=context.portableSettings(original,keys);
assert.equal(original.credentials.length,0);assert.equal(exported.credentials[0].purpose,'ssh-key');assert.equal(context.portableSettings(exported,keys).credentials.length,1);
assert.equal('privateKey' in exported.credentials[0],false);
console.log('PASS: portable settings include existing bws references without changing the source or duplicating keys');
