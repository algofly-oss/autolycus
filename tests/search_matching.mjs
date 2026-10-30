import fs from 'node:fs';
import assert from 'node:assert/strict';
import Fuse from '../ui/node_modules/fuse.js/dist/fuse.mjs';
const source = fs.readFileSync(new URL('../ui/src/components/User/components/Search/utils.js', import.meta.url), 'utf8');
const u = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const rows = u.sortResults([
  {Title:'Tensei Sitara Ken Dashita', Seeders:1000},
  {Title:'Something HinDi 1080p', Seeders:20},
  {Title:'Another [Hindi-English]', Seeders:50},
  {Title:'Hindustan release', Seeders:200},
  {Title:'Hind Movie', Seeders:400},
], u.INITIAL_SORT);
const fuse = new Fuse(rows, {...u.FUSE_OPTIONS, getFn:(item,path)=>path.join('.')==='SearchTitle'?u.normalizeSearchText(item.Title):item.Title});
assert.deepEqual(u.filterByTitle({activeSource:u.ALL_SOURCES,fuse,results:rows,titleFilter:'Hindi'}).map(row=>row.Seeders),[50,20]);
assert(u.matchesTitleWords('Café.Society.1080p.HINDI','cafe hindi'));
assert(u.matchesTitleWords('Ubuntu Desktop','Ubunto'));
assert(!u.matchesTitleWords('Desktop','Desktapz'));
assert(!u.matchesTitleWords('C language','C++'));
assert(!u.matchesTitleWords('Hindi','Hind'));
assert(u.matchesTitleWords('C++ Complete','C++'));
assert(!u.matchesTitleWords('Hindi movie','Hindi software'));
console.log('PASS: Hindi excludes unrelated anime and partial words; long-word typo tolerance, punctuation, accents, all query words, seed ordering');
const cases = [
  ['Hindi','Movie.Hindi.1080p',true], ['Hindi','Movie Hindi-English',true],
  ['Hindi','Tensei Shitara Ken Deshita',false], ['Hindi','Hindustan',false],
  ['Hindi','Shinobi',false], ['Hindi','Finding Nemo',false],
  ['comedy','Romantic Comedy Collection',true], ['comedy','Comedy Central Special',true],
  ['comedy','Comey Interview',false], ['action','Live Action Movie',true],
  ['action','Reaction Compilation',false], ['thriller','Crime Thriller',true],
  ['thriller','Thriler Movie',true], ['The Matrix','The.Matrix.1999.1080p',true],
  ['The Matrix 1999','The Matrix 1999 Remastered',true],
  ['The Matrix 1999','The Matrix 2021',false], ['The Matrix','The Matriix 1999',true],
  ['The Matrix','The Matrxi 1999',true], ['Dune 2021','Dune 2024',false],
  ['Dune 2024','Dune 2024 2160p',true], ['1999','Movie 1999',true],
  ['1999','Movie 11999',false], ['2025','Movie 2024',false],
  ['Breaking Bad','Breaking.Bad.S01E01',true],
  ['Breaking Bad S01','Breaking.Bad.S01E01.720p',true],
  ['Breaking Bad S01','Breaking.Bad.S02E01',false],
  ['Breaking Bad S01E01','Breaking.Bad.S01E02',false],
  ['Game of Thrones','Game.of.Thrones.S01',true],
  ['Star Trek','Star Wars',false], ['Office US','Office UK',false],
  ['Café Society','Cafe.Society.2016',true], ['Spider Man','Spider-Man.2002',true],
  ['C++','C++ Complete Course',true], ['C++','C# Course',false],
  ['Ubuntu 24.04','Ubuntu.24.04.Desktop',true], ['Ubuntu 24.04','Ubuntu 22.04',false],
  ['Hindi','[Hindi+English] Movie',true], ['Hindi','RD02DualAudioHindi480pBluRay400MB',true],
  ['Ubuntu 24.04','Ubuntu 14.04.24',false], ['Ubuntu 24.04','Ubuntu 24.04.1',true],
  ['2025','Movie 12025',false], ['1999','Movie (1999年)',true],
  ['Blender 4.0','Blender 4.1',false], ['Blender 4.0','Blender 4.0.2',true],
  ['Blender 4.0','Blender 4 0 0 Portable',true], ['Ubuntu 24.04','Ubuntu 24 04',true],
  ['Blender 4.0','Blender 2024.0',false], ['Blender 4.0','Blender 2024 4.0',true],
  ['VLC','VLC Media Player',true], ['VLC','Vocal Course',false],
  ['Photoshop 2024','Adobe Photoshop 2024',true], ['Photoshop 2024','Adobe Photoshop 2023',false],
];
for (const [query,title,expected] of cases) assert.equal(u.matchesTitleWords(title,query),expected,`${query} / ${title}`);
// Every short keyword must resist one-letter substitutions and substring matches.
let negatives=0;
for (const query of ['hindi','dune','s01','horror','action']) {
  for (const prefix of ['pre','post','un','abc']) {
    assert(!u.matchesTitleWords(prefix+query,query),`${prefix+query} / ${query}`); negatives++;
  }
}
console.log(`PASS: ${cases.length} curated movie, language, mood, year, series, season, software cases; ${negatives} substring negatives`);
for (const [query,title,expected] of cases) {
  const results=[{Title:title}];
  const fuse=new Fuse(results,{...u.FUSE_OPTIONS,getFn:(item,path)=>path.join('.')==='SearchTitle'?u.normalizeSearchText(item.Title):item.Title});
  assert.equal(u.filterByTitle({activeSource:u.ALL_SOURCES,fuse,results,titleFilter:query}).length>0,expected,`Full Fuse pipeline: ${query} / ${title}`);
}
console.log('PASS: all curated cases also pass the complete Fuse + secondary filter pipeline');
const musafirRows=[{Title:'Musafir 2004 Hindi',SearchResultKey:'musafir',SearchSource:'a',SearchCached:true,Seeders:1},{Title:'Hindi Other Title',SearchResultKey:'other',SearchSource:'a',SearchCached:true}];
const musafirFuse=new Fuse(musafirRows,{...u.FUSE_OPTIONS,getFn:(item,path)=>path.join('.')==='SearchTitle'?u.normalizeSearchText(item.Title):item.Title});
for(const prefix of ['m','mu','mus','musa','musafir']) {
  assert(u.filterByTitle({activeSource:u.ALL_SOURCES,fuse:musafirFuse,results:musafirRows,titleFilter:prefix,allowPrefix:true}).some(row=>row.Title.startsWith('Musafir')),prefix);
}
assert.equal(u.filterByTitle({activeSource:u.ALL_SOURCES,fuse:musafirFuse,results:musafirRows,titleFilter:'mus',allowPrefix:false}).length,0);
let merged=u.mergeSearchResults(musafirRows,[{Title:'Musafir 2004 Hindi',SearchResultKey:'musafir',SearchSource:'a',SearchCached:false,Seeders:50}]);
assert.equal(merged.length,2);assert.equal(merged[0].Seeders,50);
merged=merged.filter(row=>row.SearchSource!=='a'||!row.SearchCached);
assert.equal(merged.length,1);
assert.equal(u.mergeSearchResults(merged,[{Title:'Musafir 2004 Hindi',SearchResultKey:'other-source',SearchSource:'b'}]).length,2);
console.log('PASS: m → mu → mus keeps Musafir; cached rows update without duplicates, disappeared rows clear, separate sources retained');
