const pptxgen = require('pptxgenjs');
const { warnIfSlideHasOverlaps, warnIfSlideElementsOutOfBounds } = require('/home/oai/skills/slides/pptxgenjs_helpers');
const path = require('path');
const fs = require('fs');

const pptx = new pptxgen();
pptx.defineLayout({ name: 'CUSTOM_WIDE', width: 13.333, height: 7.5 });
pptx.layout = 'CUSTOM_WIDE';
pptx.author = 'Team 17';
pptx.company = 'Cornell MSBA Capstone';
pptx.subject = 'Revised Results, Insights Summary, and Implementation Plan';
pptx.title = 'VC Scout - Revised Results, Insights, and Implementation Plan';
pptx.lang = 'en-US';
pptx.theme = { headFontFace: 'Aptos Display', bodyFontFace: 'Aptos', lang: 'en-US' };
pptx.margin = 0;

const W = 13.333, H = 7.5;
const A = '/mnt/data/vc_scout_final_assets';
const C = {
  bg:'0E1320', bg2:'101827', card:'172236', card2:'1D2A42', card3:'121C2E', line:'2A3958',
  ink:'F4F7FB', muted:'A8B3C5', faint:'68758B', cyan:'45D4FF', green:'7EE787', amber:'FFB84D', red:'FF6B6B', purple:'B58CFF', white:'FFFFFF'
};
const shape = pptx.ShapeType;
function p(name){ return path.join(A, name); }
function addBase(s, kicker, title, subtitle, num){
  s.background = {color:C.bg};
  // deliberately decorative, kept behind content
  s.addShape(shape.rect,{x:0,y:0,w:W,h:H,fill:{color:C.bg},line:{color:C.bg,transparency:100}});
  s.addShape(shape.rect,{x:0,y:0,w:W,h:0.10,fill:{color:C.cyan,transparency:7},line:{color:C.cyan,transparency:100}});
  s.addShape(shape.rect,{x:0,y:0.10,w:3.7,h:0.03,fill:{color:C.purple,transparency:15},line:{color:C.purple,transparency:100}});
  s.addText(kicker.toUpperCase(),{x:0.47,y:0.30,w:3.3,h:0.20,fontSize:8.3,bold:true,charSpace:1.2,color:C.cyan,margin:0,fit:'shrink'});
  s.addText(title,{x:0.47,y:0.58,w:9.6,h:0.43,fontFace:'Aptos Display',fontSize:23.5,bold:true,color:C.ink,margin:0,fit:'shrink'});
  if(subtitle){s.addText(subtitle,{x:0.47,y:1.03,w:10.8,h:0.22,fontSize:10.2,color:C.muted,margin:0,fit:'shrink'});}
  s.addText('Team 17  |  Startup Growth & Investment  |  VC Scout', {x:0.47,y:7.17,w:8.2,h:0.15,fontSize:7.3,color:C.faint,margin:0});
  s.addText(String(num).padStart(2,'0'), {x:12.50,y:7.13,w:0.42,h:0.18,fontSize:8,bold:true,color:C.faint,align:'right',margin:0});
}
function card(s,x,y,w,h,title,body,accent=C.cyan,opts={}){
  s.addShape(shape.roundRect,{x,y,w,h,rectRadius:0.08,fill:{color:opts.fill||C.card},line:{color:C.line,transparency:12}});
  s.addShape(shape.rect,{x:x,y:y,w:0.05,h:h,fill:{color:accent},line:{color:accent,transparency:100}});
  s.addText(title,{x:x+0.18,y:y+0.14,w:w-0.36,h:0.23,fontSize:opts.titleSize||10.7,bold:true,color:C.ink,margin:0,fit:'shrink'});
  s.addText(body,{x:x+0.18,y:y+0.46,w:w-0.36,h:h-0.56,fontSize:opts.bodySize||8.4,color:C.muted,margin:0.01,breakLine:false,fit:'shrink'});
}
function stat(s,x,y,w,value,label,accent=C.cyan){
  s.addShape(shape.roundRect,{x,y,w,h:0.82,rectRadius:0.08,fill:{color:C.card},line:{color:C.line,transparency:10}});
  s.addText(value,{x:x+0.14,y:y+0.10,w:w-0.28,h:0.27,fontFace:'Aptos Display',fontSize:20,bold:true,color:accent,margin:0,fit:'shrink'});
  s.addText(label,{x:x+0.14,y:y+0.48,w:w-0.28,h:0.18,fontSize:7.7,color:C.muted,margin:0,fit:'shrink'});
}
function smallLabel(s,x,y,text,accent=C.cyan){
  s.addShape(shape.roundRect,{x,y,w:1.2,h:0.25,rectRadius:0.05,fill:{color:accent,transparency:10},line:{color:accent,transparency:100}});
  s.addText(text,{x:x+0.07,y:y+0.055,w:1.06,h:0.1,fontSize:7.1,bold:true,color:C.bg,align:'center',margin:0,fit:'shrink'});
}
function img(s,name,x,y,w,h){
  s.addShape(shape.roundRect,{x:x-0.03,y:y-0.03,w:w+0.06,h:h+0.06,rectRadius:0.06,fill:{color:'101827'},line:{color:C.line,transparency:15}});
  s.addImage({path:p(name),x,y,w,h});
}
function table(s,rows,x,y,w,h,widths,font=7.4){
  const rh=h/rows.length;
  rows.forEach((r,i)=>{
    const fill=i===0?C.card2:(i%2?C.card:C.card3);
    s.addShape(shape.rect,{x,y:y+i*rh,w,h:rh,fill:{color:fill},line:{color:C.line,transparency:15}});
    let cur=x;
    r.forEach((cell,j)=>{
      const cw=w*widths[j];
      s.addText(String(cell),{x:cur+0.07,y:y+i*rh+0.07,w:cw-0.12,h:rh-0.10,fontSize:i===0?7.8:font,bold:i===0,color:i===0?C.ink:C.muted,margin:0,fit:'shrink'});
      cur+=cw;
    });
  });
}
function bulletList(s, items, x,y,w,h, accent=C.cyan){
  const gap = h/items.length;
  items.forEach((it,i)=>{
    s.addShape(shape.ellipse,{x:x,y:y+i*gap+0.05,w:0.10,h:0.10,fill:{color:accent},line:{color:accent,transparency:100}});
    s.addText(it,{x:x+0.18,y:y+i*gap,w:w-0.18,h:gap-0.02,fontSize:8.5,color:C.muted,margin:0,fit:'shrink'});
  });
}

// 1. Title
let s = pptx.addSlide();
s.background={color:C.bg};
s.addShape(shape.rect,{x:0,y:0,w:W,h:H,fill:{color:C.bg},line:{color:C.bg,transparency:100}});
s.addShape(shape.rect,{x:0,y:0,w:W,h:0.12,fill:{color:C.cyan,transparency:7},line:{color:C.cyan,transparency:100}});
s.addText('REVISED RESULTS', {x:0.62,y:0.56,w:3.2,h:0.21,fontSize:10,bold:true,charSpace:1.4,color:C.cyan,margin:0});
s.addText('VC Scout', {x:0.62,y:1.00,w:5.8,h:0.58,fontFace:'Aptos Display',fontSize:36,bold:true,color:C.ink,margin:0});
s.addText('Revised Results, Insights Summary, and Implementation Plan', {x:0.62,y:1.62,w:8.2,h:0.34,fontSize:15.5,color:C.muted,margin:0});
s.addText('Startup Growth and Investment  |  Expanded Dataset Audit + Audited Benchmark Model', {x:0.62,y:2.05,w:9.5,h:0.20,fontSize:9.3,color:C.faint,margin:0});
stat(s,0.62,3.00,1.75,'75,230','expanded rows audited',C.cyan);
stat(s,2.55,3.00,1.75,'950','unit-suspect funding rows flagged/corrected',C.amber);
stat(s,4.48,3.00,1.75,'1,829','rows with valuation',C.purple);
stat(s,6.41,3.00,1.55,'0.30','audited test R²',C.green);
stat(s,8.14,3.00,1.65,'0.49','funding elasticity',C.cyan);
stat(s,9.97,3.00,1.60,'77%','noisy Form D mega dollars',C.red);
card(s,0.62,4.48,11.0,0.96,'Executive answer','VC Scout should be implemented as a benchmark-and-scouting framework, not a startup-success prediction engine. The revised work audits the expanded data, preserves traceability, and shifts the insight from raw valuation to funding-adjusted outperformance.',C.green,{bodySize:9.0});
s.addText('Team 17', {x:0.62,y:6.04,w:1.0,h:0.20,fontSize:11.5,bold:true,color:C.ink,margin:0});
s.addText('Mia Murphy  •  Finn Kliewer  •  Kayvon Jafarzadeh  •  Nathanael Gill  •  Om Patel', {x:0.62,y:6.34,w:8.1,h:0.18,fontSize:9.3,color:C.muted,margin:0});
s.addText('Submission package includes PPTX/PDF plus auditable CSVs, source-of-truth JSON, and a reproducible Python script.', {x:0.62,y:6.78,w:10.5,h:0.17,fontSize:7.8,color:C.faint,margin:0});

// 2. Deliverable focus
s = pptx.addSlide(); addBase(s,'Deliverable focus','What changed since the prior submission','The prior work established EDA and a first valuation model; this submission turns that into a defensible implementation plan.',2);
card(s,0.58,1.48,3.85,1.42,'Refined tools and models','We landed on a two-layer architecture: an audited unicorn valuation benchmark plus an expanded-tier diagnostic layer. Gradient Boosting remains the benchmark champion, while OLS/Ridge remain interpretability checks.',C.cyan);
card(s,4.74,1.48,3.85,1.42,'Shortcomings addressed','The expanded data adds useful controls, but it also introduces funding-unit risk, source/timing mismatch, missing valuation coverage, and noisy Form D entities. We address these through flags, corrections, and decision boundaries.',C.amber);
card(s,8.90,1.48,3.85,1.42,'Insights and hypotheses','The analysis now tests 2021 as a market-regime shock, validates diminishing returns to funding, stress-tests no-funding scouting, and uses residuals to identify outperformance patterns.',C.green);
card(s,0.58,3.35,3.85,1.42,'Business implications','VC Scout should rank segments by benchmark outperformance, not raw valuation or raw unicorn count. This reduces hype bias and makes rankings more explainable.',C.purple);
card(s,4.74,3.35,3.85,1.42,'Implementation plan','The final deliverable should include a transparent scoring layer, sample-size confidence flags, investor network features, and a dashboard/dashboard-style slide for business users.',C.green);
card(s,8.90,3.35,3.85,1.42,'Traceability standard','Every number in the deck maps to a cleaned CSV, model output file, source-of-truth JSON, or reproducible script. The goal is to avoid black-box reporting.',C.cyan);
card(s,0.58,5.40,12.17,0.95,'Framing shift','From predict unicorn valuation to identifying funding-adjusted valuation outperformance signals among unicorn and comparable startup tiers.',C.green,{titleSize:10.5,bodySize:8.8});

// 3. Data audit
s = pptx.addSlide(); addBase(s,'Data shortcomings','Expanded data improves the project only after an audit','This is where the revised analysis directly addresses data quality and survivorship-bias risk.',3);
img(s,'audit_coverage_final.png',0.62,1.45,5.05,3.25);
card(s,6.05,1.45,3.02,1.15,'Coverage limitation','Only 1,829 of 75,230 rows have valuation. This prevents valuation modeling across the full startup universe.',C.purple);
card(s,9.42,1.45,3.02,1.15,'Funding unit risk','950 unicorn rows were flagged because funding exceeded valuation, indicating a likely M/B scaling issue in the expanded build.',C.amber);
card(s,6.05,3.03,3.02,1.15,'Form D noise','Raw Form D includes many funds, real estate entities, and finance vehicles. It is retained as market context, not a clean startup-training set.',C.red);
card(s,9.42,3.03,3.02,1.15,'Survivorship remains','The expanded master adds comparison tiers but is not a time-aligned panel of all startups from formation to outcome.',C.green);
card(s,0.62,5.30,11.82,0.72,'How we addressed it','The cleaned master preserves raw values, adds audited funding, assigns audit flags, isolates Form D, and separates unicorn valuation benchmarking from broader tier diagnostics.',C.cyan,{bodySize:9});

// 4. 2021 / COVID-era trend
s = pptx.addSlide(); addBase(s,'Hypothesis H1','2021 is a market-regime shock, not a normal trend line','The data flags the discontinuity; it does not prove COVID causality by itself.',4);
img(s,'era_year_counts_final.png',0.62,1.46,5.55,3.10);
img(s,'era_medians_final.png',6.55,1.46,5.70,3.10);
card(s,0.62,5.05,3.65,1.12,'What is proven','2021 is the largest single dated current-unicorn cohort in the expanded data, and era differences in valuation, funding, and sector mix are statistically significant.',C.green,{bodySize:8.3});
card(s,4.54,5.05,3.65,1.12,'What is not proven','The dataset alone cannot separate COVID-driven demand, cheap capital, investor behavior, or valuation inflation as causal explanations.',C.amber,{bodySize:8.3});
card(s,8.46,5.05,3.65,1.12,'Action for VC Scout','Keep a 2021/era indicator and show users when a benchmark is influenced by an unusual funding regime.',C.cyan,{bodySize:8.3});

// 5. Tools and model architecture
s = pptx.addSlide(); addBase(s,'Tools landed on','Two-layer analytics architecture','The tools are chosen to match what the data can support, not what sounds most sophisticated.',5);
card(s,0.75,1.58,5.55,1.28,'Layer A: audited unicorn valuation benchmark','Supervised regression on ln(valuation) for unicorn-history rows with audited funding. Gradient Boosting captures nonlinearity; OLS/Ridge provide explainability and elasticity checks.',C.cyan,{bodySize:8.4});
card(s,7.02,1.58,5.55,1.28,'Layer B: expanded-tier diagnostic model','Classifier compares unicorn-history companies with funded controls, accelerator controls, and high-funding proxies. It is useful for screening patterns, not causal winner prediction.',C.green,{bodySize:8.4});
// flow labels
smallLabel(s,2.32,3.30,'Benchmark',C.cyan);
smallLabel(s,5.13,3.30,'Residuals',C.purple);
smallLabel(s,7.95,3.30,'Scoring',C.green);
smallLabel(s,10.77,3.30,'Decision',C.amber);
card(s,1.00,4.06,2.65,1.02,'Model output','Expected valuation given funding, sector, geography, era, tier, speed, and investors.',C.cyan,{bodySize:7.8});
card(s,3.82,4.06,2.65,1.02,'Insight output','Actual minus expected valuation identifies funding-adjusted outperformance.',C.purple,{bodySize:7.8});
card(s,6.64,4.06,2.65,1.02,'VC Scout score','Blend residuals, tier signal, sample size, data confidence, and investor network features.',C.green,{bodySize:7.8});
card(s,9.46,4.06,2.65,1.02,'User action','Prioritize sector/region/investor clusters for deeper diligence, not automatic investing.',C.amber,{bodySize:7.8});
card(s,0.75,6.00,11.82,0.52,'Guardrail','No claim of “probability of becoming a unicorn” until there is a true time-aligned non-unicorn panel with observed outcomes.',C.red,{titleSize:9.5,bodySize:7.7});

// 6. Revised model results
s = pptx.addSlide(); addBase(s,'Revised results','The audited benchmark has modest but credible signal','The important result is not a perfect model; it is a defendable benchmark engine.',6);
img(s,'model_results_final.png',0.62,1.43,5.55,3.22);
img(s,'funding_elasticity_final.png',6.52,1.43,5.75,3.22);
card(s,0.62,5.12,2.85,1.08,'Champion','Gradient Boosting remains preferred after the audit: test R² ~= 0.30. This is lower than the earlier Kaggle-only result, but more defensible.',C.green,{bodySize:7.55});
card(s,3.72,5.12,2.85,1.08,'Funding effect','Funding remains important, but elasticity ~= 0.49 means valuation rises less than one-for-one with capital raised.',C.cyan,{bodySize:8.2});
card(s,6.82,5.12,2.85,1.08,'No-funding stress test','Removing funding drops R² to about 0.05, showing early-stage scouting is much harder than late-stage benchmarking.',C.amber,{bodySize:8.2});
card(s,9.92,5.12,2.35,1.08,'Implication','Use model residuals and segment signals, not exact point estimates.',C.purple,{bodySize:8.0});

// 7. Hypothesis summary
s = pptx.addSlide(); addBase(s,'Insights developed','Hypotheses proven, disproven, and carried forward','This turns the analysis into decision-ready learning, not just charts.',7);
table(s,[
  ['Hypothesis','Status','Evidence / implication'],
  ['H1: 2021 is a distinct regime','Supported','Largest dated cohort; valuation/funding distributions and sector mix differ by era. Interpret as market-regime signal, not proof of COVID causality.'],
  ['H2: Funding has diminishing returns','Supported','Audited log-log elasticity ~= 0.49. More capital helps, but raw funding does not scale valuation one-for-one.'],
  ['H3: Sector/geography add signal','Partially supported','Residual tables show directional variation, but thin samples need confidence flags before ranking.'],
  ['H4: Expanded controls solve survivorship bias','Disproven / partial','The 75k-row master helps context, but source timing, missing valuation, and proxy labels remain.'],
  ['H5: Investor count captures network quality','Not proven','Investor count is too crude; final model should use top-fund flags and co-investor clusters.']
],0.62,1.50,12.05,4.68,[0.25,0.18,0.57],7.3);
card(s,0.62,6.25,12.05,0.82,'Next analytic emphasis','Move from company-level valuation prediction to segment-level outperformance, where data quality and sample-size caveats can be surfaced honestly.',C.green,{titleSize:9.6,bodySize:8.1});

// 8. Residual insights
s = pptx.addSlide(); addBase(s,'Insight engine','Residuals turn a model into VC Scout','Actual minus expected valuation is the cleanest bridge from statistics to business action.',8);
img(s,'industry_residuals_final.png',0.60,1.43,5.90,3.20);
img(s,'country_residuals_final.png',6.78,1.43,5.55,3.20);
card(s,0.60,5.15,3.70,1.04,'How to read it','Positive residuals mean a segment exceeds expected valuation after adjusting for funding and context.',C.green,{bodySize:8.1});
card(s,4.55,5.15,3.70,1.04,'What is useful','Residuals create watchlists: segments worth deeper diligence because they outperform a fair benchmark.',C.cyan,{bodySize:8.1});
card(s,8.50,5.15,3.70,1.04,'What to avoid','Do not treat small-n residual leaders as final rankings. Add confidence and sample-size penalties.',C.amber,{bodySize:8.1});

// 9. Expanded tier diagnostic
s = pptx.addSlide(); addBase(s,'Expanded-tier diagnostic','High accuracy can be a warning sign','The classifier can screen patterns, but it can also learn source artifacts.',9);
s.addText('Expanded-tier classifier: high diagnostic accuracy, high bias risk',{x:0.72,y:1.40,w:5.35,h:0.20,fontSize:10.8,color:C.ink,align:'center',margin:0,fit:'shrink'});
// Native legend kept outside the chart so it cannot overlap the bars.
const lgY = 1.67;
[[C.cyan,'ROC AUC'],[C.green,'Balanced accuracy'],[C.purple,'Avg precision']].forEach((d,i)=>{
  const lx = 1.58 + i*1.33;
  s.addShape(shape.rect,{x:lx,y:lgY,w:0.16,h:0.07,fill:{color:d[0]},line:{color:d[0],transparency:100}});
  s.addText(d[1],{x:lx+0.20,y:lgY-0.025,w:1.05,h:0.13,fontSize:7.4,color:C.muted,margin:0,fit:'shrink'});
});
img(s,'tier_classifier_final.png',0.62,1.86,5.75,2.75);
card(s,6.78,1.50,2.75,1.12,'Tempting read','The model separates unicorn-history rows from controls with very high diagnostic accuracy.',C.green,{bodySize:8.1});
card(s,9.86,1.50,2.75,1.12,'Statistician read','Some of that signal is likely source/timing bias, not true startup destiny.',C.red,{bodySize:8.1});
card(s,6.78,3.05,2.75,1.12,'Safe use','Use expanded-tier scores to prioritize sectors and questions for diligence.',C.cyan,{bodySize:8.1});
card(s,9.86,3.05,2.75,1.12,'Unsafe use','Do not claim this predicts arbitrary startups becoming unicorns.',C.amber,{bodySize:8.1});
card(s,0.62,5.35,12.0,0.72,'Implementation decision','The expanded dataset belongs in VC Scout as a diagnostic comparison layer and confidence input, not as the sole basis for a success-probability model.',C.purple,{bodySize:8.8});

// 10. Business recommendations
s = pptx.addSlide(); addBase(s,'Business actions','Initial recommendations for a VC Scout user','The recommendations are deliberately decision-support oriented.',10);
card(s,0.62,1.45,3.75,1.25,'1. Rank outperformance, not size','Raw valuation and raw unicorn count are too sensitive to capital intensity and market cycles. Rank segments against expected valuation benchmarks.',C.cyan,{bodySize:8.0});
card(s,4.78,1.45,3.75,1.25,'2. Keep 2021 visible','Treat 2021 as a market-regime flag. Do not let one unusual funding period define “normal” scouting baselines.',C.amber,{bodySize:8.0});
card(s,8.94,1.45,3.75,1.25,'3. Use residuals as watchlists','Sectors, countries, or investor clusters with repeated positive residuals become candidates for deeper diligence.',C.green,{bodySize:8.0});
card(s,0.62,3.25,3.75,1.25,'4. Add confidence labels','Every score should show sample size, data coverage, and whether the signal depends heavily on audited/corrected fields.',C.purple,{bodySize:8.0});
card(s,4.78,3.25,3.75,1.25,'5. Upgrade investor features','Replace investor count with top-fund flags, sector specialization, co-investor networks, and timing of involvement.',C.green,{bodySize:8.0});
card(s,8.94,3.25,3.75,1.25,'6. Separate model from diligence','The tool narrows the search space. Final investment judgments still require revenue, retention, burn, TAM, and ownership data.',C.red,{bodySize:8.0});
card(s,0.62,5.75,12.07,0.60,'Recommended positioning','VC Scout is a market-intelligence and prioritization tool, not an automated investment recommender.',C.cyan,{titleSize:9.8,bodySize:7.8});

// 11. Implementation plan and audit trail
s = pptx.addSlide(); addBase(s,'Implementation plan','What gets built before in-person week','The final submission should be traceable enough that every number can be defended.',11);
table(s,[
  ['Sprint','Workstream','Concrete output'],
  ['1','Data QA hardening','Finalize audited master, funding audit rule, source notes, and Form D exclusion/context logic.'],
  ['2','Benchmark model','Lock audited valuation benchmark, residual outputs, and no-funding stress test.'],
  ['3','VC Scout score','Combine residual outperformance, tier signal, sector/geography medians, sample-size penalty, and data confidence.'],
  ['4','Dashboard / slideware','Build final user-facing view: sector, region, investor cluster, confidence, and limitations.'],
  ['5','Final review','Package PPTX/PDF, cleaned CSVs, source-of-truth JSON, and reproducible script for auditability.']
],0.62,1.45,7.65,3.65,[0.12,0.28,0.60],7.4);
card(s,8.62,1.45,3.85,1.12,'Deliverable structure','PowerPoint/PDF for stakeholders; audit-trail ZIP for the professor or anyone asking for raw analysis.',C.green,{bodySize:8.2});
card(s,8.62,2.95,3.85,1.12,'Final model language','“Funding-adjusted valuation outperformance signal” stays defensible and avoids unsupported causal success claims.',C.cyan,{bodySize:8.2});
card(s,8.62,4.45,3.85,1.12,'Remaining data need','A true success model requires a time-aligned startup panel with non-unicorns, failures, acquisitions, and follow-on outcomes.',C.amber,{bodySize:8.2});
card(s,0.62,6.10,11.85,0.88,'Audit-trail files','Audited master CSV, Form D audited CSV, model results CSV, residual tables, hypothesis summary, source-of-truth JSON, and analysis script.',C.purple,{titleSize:9.6,bodySize:8.0});

function validateDeck(){
  for (const slide of pptx._slides) {
    warnIfSlideHasOverlaps(slide, pptx, { muteContainment:true, ignoreDecorativeShapes:true });
    warnIfSlideElementsOutOfBounds(slide, pptx);
  }
}
validateDeck();
pptx.writeFile({ fileName:'/mnt/data/team17_vc_scout_revised_results_insights_implementation_final.pptx' });
