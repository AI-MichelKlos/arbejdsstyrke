const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const html=fs.readFileSync('index.html','utf8');
for(const [i,match] of [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].entries()){
  if(match[1].trim())new vm.Script(match[1],{filename:'inline-'+i+'.js'});
}
assert(!html.includes('const age67=m('),'Old 67-year spotlight must not remain');
assert(!html.includes('const pensionOwn='),'Pension KPI must not switch categories by age');
assert(!html.includes('Grafik og databehandling: Danske A-kasser'),'Author credit must be Michel Klos');
console.log('Embedded JavaScript and attribution syntax checks passed');
(async()=>{
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1280,height:900},deviceScaleFactor:1});
  const failures=[];
  page.on('pageerror',error=>failures.push(error.message));
  try{
    await page.goto('http://127.0.0.1:8765/index.html',{waitUntil:'domcontentloaded',timeout:60000});
    await page.waitForFunction(()=>document.querySelector('#k-share')?.textContent.includes('pct.')&&document.querySelector('#age-sub')?.textContent.includes('valgt aldersgruppe'),null,{timeout:90000});
    const view=async(age,label)=>{
      await page.selectOption('#age',age);
      await page.waitForFunction(label=>document.querySelector('#selection')?.textContent.includes(label)&&document.querySelector('#age-sub')?.textContent.includes(label)&&document.querySelector('main')?.getAttribute('aria-busy')==='false',label,{timeout:90000});
      const result=await page.evaluate(()=>({
        age:document.querySelector('#selection')?.textContent,
        title:document.querySelector('#age-title')?.textContent,
        ageDescription:document.querySelector('#age-sub')?.textContent,
        pensionFolk:document.querySelector('#k-pension-folk')?.textContent,
        pensionOwn:document.querySelector('#k-pension-own')?.textContent,
        pensionChartNote:document.querySelector('#pension-note')?.textContent,
        degreeContext:document.querySelector('#degree-chart')?.closest('article')?.querySelector('.chart-context')?.textContent,
        statusContext:document.querySelector('#status-sub')?.textContent,
        highlights:['age-chart','degree-chart','status-chart'].map(id=>!!window.Chart?.getChart(document.getElementById(id))?.config.plugins?.some(p=>p.id==='ageSelectionBand'))
      }));
      assert(!result.title.includes('67-årige'),JSON.stringify(result));
      assert(result.highlights.every(Boolean),'Selected group must be highlighted on figures 2, 5 and 6');
      assert(result.degreeContext.includes(label)&&result.statusContext.includes(label));
      assert(result.pensionFolk&&result.pensionOwn&&result.pensionChartNote,'Pension KPIs and note missing');
      console.log('PASS',age,JSON.stringify(result));
      return result;
    };
    const basic=await view('60-64','60-64 år');
    assert(basic.pensionOwn!=='Ikke tilgængelig','The own-pension group should have observed data');
    const mixed=await view('65-69','65-69 år');
    assert(mixed.pensionFolk==='Ikke tilgængelig','A mixed group with unavailable source values must not report partial folk-pension counts');
    const older=await view('67-74','67-74 år');
    assert(older.pensionFolk!=='Ikke tilgængelig','67-74 folk-pension should be calculable with complete input');
    await view('55-74','55-74 år');
    await view('75-75','75+ år');
    assert((await page.locator('#map-sub').textContent()).includes('12-månedersgennemsnit'),'Map must explain its reference period');
    assert(!failures.length,'Browser errors: '+failures.join(' | '));
    console.log('Senior dashboard age tests passed');
  }finally{await browser.close();}
})().catch(err=>{console.error(err);process.exit(1);});
