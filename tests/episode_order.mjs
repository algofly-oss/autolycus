import assert from 'node:assert/strict';
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
const source=fs.readFileSync(new URL('../ui/src/shared/episodeOrder.js',import.meta.url),'utf8');
const {sortEpisodes}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const paths=[
 'Show/Season 10/Show.S10E01.mkv','Show/Season 2/Show.S02E10.mkv',
 'Show/Season 1/Show.1x02.Pilot.mkv','Show/Season 2/Episode 02 - Pilot.mkv',
 'Show/Season 1/Show.S01E01.mkv','Show/Season 2/Show.S02E01.mkv',
 'Show/Season 1/Show.S00E01.Special.mkv','Show/Season 1/Show.S01E03-E04.mkv',
];
const identities=JSON.parse(execFileSync('python',['-c','import json,sys;sys.path.insert(0,"api");from shared.modules.media_filename import episode_identity;print(json.dumps([episode_identity(p) for p in json.loads(sys.argv[1])]))',JSON.stringify(paths)],{cwd:new URL('..',import.meta.url),env:{...process.env,PYTHONWARNINGS:'ignore'}}));
const entries=paths.map((path,i)=>({path,label:path,name:path.split('/').at(-1),episodeInfo:identities[i]}));
const expected=[6,4,2,7,5,3,1,0].map(i=>paths[i]);
assert.deepEqual(sortEpisodes(entries).map(e=>e.path),expected);
for(let i=0;i<20;i++)assert.deepEqual(sortEpisodes([...entries].sort(()=>Math.random()-.5)).map(e=>e.path),expected);
const fallback=['Folder/file10.mp4','Folder/file2.mp4','Folder/file1.mp4'].map(path=>({path,label:path}));
assert.deepEqual(sortEpisodes(fallback).map(e=>e.path),['Folder/file1.mp4','Folder/file2.mp4','Folder/file10.mp4']);
console.log('PASS: PTN-backed mixed SxxExx / NxEE / episode-only ordering across season folders, specials, ranges and natural fallback');
