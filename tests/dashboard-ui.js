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
