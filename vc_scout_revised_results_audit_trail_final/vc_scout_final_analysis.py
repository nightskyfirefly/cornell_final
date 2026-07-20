import json, warnings, zipfile, shutil
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats
from sklearn.model_selection import train_test_split, StratifiedShuffleSplit, cross_val_score
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge, LogisticRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error, roc_auc_score, average_precision_score, balanced_accuracy_score, precision_score, recall_score
from sklearn.inspection import permutation_importance

warnings.filterwarnings('ignore')
np.random.seed(17)
DATA = Path('/mnt/data')
OUT = Path('/mnt/data/vc_scout_final_assets')
OUT.mkdir(exist_ok=True)

sm = pd.read_csv(DATA/'startup_master.csv', low_memory=False)
fd = pd.read_csv(DATA/'formd_2026q2_raises.csv')
summary = json.loads((DATA/'build_summary.json').read_text())

# ----------------------------
# Data audit and cleanup layer
# ----------------------------
df = sm.copy()
df['valuation_usd'] = df['valuation_b_latest'] * 1e9
df['funding_original_usd'] = df['funding_total_usd']
df['funding_audited_usd'] = df['funding_total_usd']
df['funding_audit_flag'] = 'ok_or_missing'

unicorn_like = df['tier'].isin(['unicorn_current','unicorn_delisted','unicorn_exited'])
val_fund = unicorn_like & df['valuation_usd'].notna() & df['funding_original_usd'].notna() & (df['funding_original_usd'] > 0)
# Working correction: the expanded builder appears to have stored many M-denominated unicorn funding values 1,000x too large.
unit_suspect = val_fund & (df['funding_original_usd'] > df['valuation_usd'])
df.loc[unit_suspect, 'funding_audited_usd'] = df.loc[unit_suspect, 'funding_original_usd'] / 1000.0
df.loc[unit_suspect, 'funding_audit_flag'] = 'unit_suspect_unicorn_funding_gt_valuation_working_divide_by_1000'
df.loc[df['funding_original_usd'].isna(), 'funding_audit_flag'] = 'missing_funding'
df.loc[df['funding_original_usd'].fillna(-1).eq(0), 'funding_audit_flag'] = 'zero_funding_log_excluded'
post_bad = unicorn_like & df['valuation_usd'].notna() & df['funding_audited_usd'].notna() & (df['funding_audited_usd'] > df['valuation_usd'])
df.loc[post_bad, 'funding_audit_flag'] = df.loc[post_bad, 'funding_audit_flag'].astype(str) + '|still_funding_gt_valuation_review'

df['date_joined_parsed'] = pd.to_datetime(df['date_joined_unicorn'], errors='coerce')
df['unicorn_year'] = df['date_joined_parsed'].dt.year
df['years_to_unicorn'] = df['unicorn_year'] - df['founded_year']
df['years_to_unicorn_flag'] = np.where(df['years_to_unicorn'] < 0, 'negative_time_to_unicorn', '')
df['era'] = np.select([df['unicorn_year'] <= 2020, df['unicorn_year'] == 2021, df['unicorn_year'] >= 2022], ['Pre-2021','2021','Post-2021'], default='Unknown')
df['is_unicorn_history'] = unicorn_like.astype(int)

priority_cols = ['company','tier','primary_source','valuation_b_latest','valuation_usd','funding_original_usd','funding_audited_usd','funding_audit_flag','industry_raw','industry_group','country','continent','city','founded_year','date_joined_unicorn','unicorn_year','era','years_to_unicorn','years_to_unicorn_flag','outcome','investors','investor_count','accelerator','in_yc','in_techstars','in_500global']
other_cols = [c for c in df.columns if c not in priority_cols]
df[priority_cols + other_cols].to_csv(OUT/'vc_scout_audited_startup_master_final.csv', index=False)

# Form D audit
non_startup_cats = ['Investing','Other Real Estate','REITS and Finance','Insurance','Other Banking and Financial Services','Commercial Banking','Commercial','Residential','Investment Banking']
fd = fd.copy()
fd['likely_nonstartup_category'] = fd['industry_group_sec'].isin(non_startup_cats)
fd['likely_operating_company_context'] = ~fd['likely_nonstartup_category']
fd.to_csv(OUT/'vc_scout_formd_q2_2026_audited_final.csv', index=False)
mega = fd[fd['mega_raise_100m']]
mega_nonstartup = int(mega['likely_nonstartup_category'].sum())
mega_total = int(mega.shape[0])
mega_dollar_share_nonstartup = float(mega.loc[mega['likely_nonstartup_category'],'total_sold_usd'].sum() / mega['total_sold_usd'].sum()) if mega_total else np.nan

# ----------------------------
# Era / 2021 hypothesis test
# ----------------------------
u_dates = df[unicorn_like & df['unicorn_year'].notna()].copy()
era_order = ['Pre-2021','2021','Post-2021']
era_summary = u_dates.groupby('era').agg(
    dated_unicorn_rows=('company','size'),
    median_valuation_b=('valuation_b_latest','median'),
    median_funding_b=('funding_audited_usd', lambda s: np.nanmedian(s)/1e9),
    median_years_to_unicorn=('years_to_unicorn','median'),
    industries=('industry_group', lambda s: s.nunique(dropna=True))
).reindex(era_order).reset_index()
era_summary.to_csv(OUT/'vc_scout_era_regime_summary_final.csv', index=False)

year_counts = u_dates['unicorn_year'].value_counts().sort_index().rename_axis('unicorn_year').reset_index(name='count')
year_counts.to_csv(OUT/'vc_scout_unicorn_year_counts_final.csv', index=False)

def kruskal_p(col):
    groups = [u_dates.loc[u_dates['era']==e, col].dropna() for e in era_order]
    if all(len(g)>0 for g in groups):
        return float(stats.kruskal(*groups).pvalue)
    return np.nan
sector_mix = pd.crosstab(u_dates['era'], u_dates['industry_group'])
chi_sector_p = float(stats.chi2_contingency(sector_mix)[1]) if sector_mix.size else np.nan

# ----------------------------
# Valuation benchmark model
# ----------------------------
model_df = df[unicorn_like & df['valuation_usd'].notna() & df['funding_audited_usd'].notna() & (df['funding_audited_usd'] > 0)].copy()
model_df = model_df[~(model_df['years_to_unicorn'] < 0)].copy()
model_df['ln_valuation'] = np.log(model_df['valuation_usd'])
model_df['ln_funding'] = np.log(model_df['funding_audited_usd'])
for c in ['industry_group','continent','era','tier','country']:
    model_df[c] = model_df[c].fillna('Unknown').astype(str)
for c in ['years_to_unicorn','investor_count']:
    model_df[c] = model_df[c].fillna(model_df[c].median())

features = ['ln_funding','years_to_unicorn','investor_count','industry_group','continent','era','tier']
num = ['ln_funding','years_to_unicorn','investor_count']
cat = ['industry_group','continent','era','tier']
X = model_df[features]
y = model_df['ln_valuation']
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=17)

pre_tree = ColumnTransformer([
    ('num', SimpleImputer(strategy='median'), num),
    ('cat', Pipeline([('imp', SimpleImputer(strategy='most_frequent')),('oh', OneHotEncoder(handle_unknown='ignore'))]), cat)
])
pre_linear_scaled = ColumnTransformer([
    ('num', Pipeline([('imp', SimpleImputer(strategy='median')),('sc', StandardScaler())]), num),
    ('cat', Pipeline([('imp', SimpleImputer(strategy='most_frequent')),('oh', OneHotEncoder(handle_unknown='ignore'))]), cat)
])
models = {
    'OLS': Pipeline([('pre', pre_linear_scaled), ('model', LinearRegression())]),
    'Ridge': Pipeline([('pre', pre_linear_scaled), ('model', Ridge(alpha=10))]),
    'Random Forest': Pipeline([('pre', pre_tree), ('model', RandomForestRegressor(n_estimators=300, max_depth=5, min_samples_leaf=4, random_state=17))]),
    'Gradient Boosting': Pipeline([('pre', pre_tree), ('model', GradientBoostingRegressor(n_estimators=250, learning_rate=0.03, max_depth=2, subsample=0.85, random_state=17))]),
}
results = []
preds = {}
for name, pipe in models.items():
    cv_scores = cross_val_score(pipe, Xtr, ytr, scoring='r2', cv=5)
    pipe.fit(Xtr, ytr)
    pred = pipe.predict(Xte)
    preds[name] = pred
    results.append({
        'model': name,
        'cv_r2_mean': float(cv_scores.mean()),
        'cv_r2_std': float(cv_scores.std()),
        'test_r2': float(r2_score(yte, pred)),
        'mae_ln': float(mean_absolute_error(yte, pred)),
        'rmse_ln': float(mean_squared_error(yte, pred)**0.5),
        'median_abs_pct_error': float(np.median(np.abs(np.exp(pred)-np.exp(yte)) / np.exp(yte)))
    })
res = pd.DataFrame(results).sort_values('test_r2', ascending=False)
res.to_csv(OUT/'vc_scout_model_results_final.csv', index=False)
champion_name = res.iloc[0]['model']
champion = models[champion_name]

# unscaled coefficient for funding elasticity (interpretation layer)
pre_interpret = ColumnTransformer([
    ('num', 'passthrough', num),
    ('cat', Pipeline([('imp', SimpleImputer(strategy='most_frequent')),('oh', OneHotEncoder(drop='first', handle_unknown='ignore'))]), cat)
])
interpret_pipe = Pipeline([('pre', pre_interpret), ('model', LinearRegression())])
interpret_pipe.fit(X, y)
funding_elasticity = float(interpret_pipe.named_steps['model'].coef_[0])

# no-funding stress test
nf_features = ['years_to_unicorn','investor_count','industry_group','continent','era','tier']
nf_num = ['years_to_unicorn','investor_count']; nf_cat=['industry_group','continent','era','tier']
pre_nf = ColumnTransformer([
    ('num', Pipeline([('imp', SimpleImputer(strategy='median')), ('sc', StandardScaler())]), nf_num),
    ('cat', Pipeline([('imp', SimpleImputer(strategy='most_frequent')),('oh', OneHotEncoder(handle_unknown='ignore'))]), nf_cat)
])
nf_pipe = Pipeline([('pre', pre_nf), ('model', Ridge(alpha=10))])
Xtr_nf, Xte_nf = Xtr[nf_features], Xte[nf_features]
nf_pipe.fit(Xtr_nf, ytr)
nf_pred = nf_pipe.predict(Xte_nf)
no_funding_result = {'model':'No-funding Ridge diagnostic','test_r2':float(r2_score(yte,nf_pred)), 'mae_ln':float(mean_absolute_error(yte,nf_pred))}

# residual tables
model_df['pred_ln_valuation'] = champion.predict(model_df[features])
model_df['residual_ln'] = model_df['ln_valuation'] - model_df['pred_ln_valuation']
model_df['valuation_outperformance_pct'] = np.exp(model_df['residual_ln']) - 1
model_df[['company','tier','valuation_b_latest','funding_audited_usd','industry_group','country','continent','era','years_to_unicorn','investor_count','pred_ln_valuation','residual_ln','valuation_outperformance_pct']].to_csv(OUT/'vc_scout_unicorn_residuals_final.csv', index=False)

def residual_summary(col, min_n):
    t = model_df.groupby(col).agg(
        n=('company','size'),
        median_valuation_b=('valuation_b_latest','median'),
        median_funding_b=('funding_audited_usd', lambda s: np.nanmedian(s)/1e9),
        avg_residual_ln=('residual_ln','mean'),
        median_outperformance_pct=('valuation_outperformance_pct','median')
    ).reset_index()
    return t[t['n'] >= min_n].sort_values('avg_residual_ln', ascending=False)
industry_resid = residual_summary('industry_group', 8)
country_resid = residual_summary('country', 10)
continent_resid = residual_summary('continent', 10)
industry_resid.to_csv(OUT/'vc_scout_residuals_by_industry_final.csv', index=False)
country_resid.to_csv(OUT/'vc_scout_residuals_by_country_final.csv', index=False)
continent_resid.to_csv(OUT/'vc_scout_residuals_by_continent_final.csv', index=False)

# permutation importance for champion
perm = permutation_importance(champion, Xte, yte, n_repeats=10, random_state=17, scoring='r2')
perm_df = pd.DataFrame({'feature': features, 'importance_mean': perm.importances_mean, 'importance_std': perm.importances_std}).sort_values('importance_mean', ascending=False)
perm_df.to_csv(OUT/'vc_scout_permutation_importance_final.csv', index=False)

# ----------------------------
# Expanded tier diagnostic classifier
# ----------------------------
clf_df = df[df['tier'].isin(['unicorn_current','unicorn_delisted','unicorn_exited','soonicorn_proxy','control_funded','control_accelerator'])].copy()
clf_df['target_unicorn_history'] = clf_df['tier'].isin(['unicorn_current','unicorn_delisted','unicorn_exited']).astype(int)
clf_df['ln_funding_audited'] = np.where(clf_df['funding_audited_usd'].fillna(0)>0, np.log(clf_df['funding_audited_usd']), np.nan)
clf_df['founded_year'] = clf_df['founded_year'].fillna(clf_df['founded_year'].median())
clf_df['investor_count'] = clf_df['investor_count'].fillna(0)
for c in ['industry_group','country','continent','tier']:
    clf_df[c] = clf_df[c].fillna('Unknown').astype(str)
# downsample negatives 5:1 to keep diagnostics balanced enough and auditable
pos = clf_df[clf_df['target_unicorn_history']==1]
neg = clf_df[clf_df['target_unicorn_history']==0].sample(n=min(len(clf_df[clf_df['target_unicorn_history']==0]), len(pos)*5), random_state=17)
clf_s = pd.concat([pos,neg], ignore_index=True)
clf_features = ['ln_funding_audited','founded_year','investor_count','industry_group','country','continent','in_yc','in_techstars','in_500global']
clf_num=['ln_funding_audited','founded_year','investor_count']; clf_cat=['industry_group','country','continent','in_yc','in_techstars','in_500global']
Xc=clf_s[clf_features]; yc=clf_s['target_unicorn_history']
Xctr,Xcte,yctr,ycte=train_test_split(Xc,yc,test_size=0.25,random_state=17,stratify=yc)
pre_clf=ColumnTransformer([
    ('num', Pipeline([('imp', SimpleImputer(strategy='median')),('sc', StandardScaler())]), clf_num),
    ('cat', Pipeline([('imp', SimpleImputer(strategy='most_frequent')),('oh', OneHotEncoder(handle_unknown='ignore'))]), clf_cat)
])
clf_models={
    'Logistic diagnostic': Pipeline([('pre',pre_clf),('model',LogisticRegression(max_iter=1000, class_weight='balanced', random_state=17))]),
    'Gradient Boosting diagnostic': Pipeline([('pre',pre_clf),('model',GradientBoostingClassifier(n_estimators=150, learning_rate=0.04, max_depth=2, random_state=17))]),
    'Random Forest diagnostic': Pipeline([('pre',pre_clf),('model',RandomForestClassifier(n_estimators=250, max_depth=6, min_samples_leaf=5, random_state=17, class_weight='balanced'))])
}
clf_results=[]
for name,pipe in clf_models.items():
    pipe.fit(Xctr,yctr)
    prob=pipe.predict_proba(Xcte)[:,1]
    lab=(prob>=0.5).astype(int)
    clf_results.append({
        'model':name,
        'roc_auc':float(roc_auc_score(ycte,prob)),
        'avg_precision':float(average_precision_score(ycte,prob)),
        'balanced_accuracy':float(balanced_accuracy_score(ycte,lab)),
        'precision':float(precision_score(ycte,lab,zero_division=0)),
        'recall':float(recall_score(ycte,lab,zero_division=0)),
        'n_sampled':int(len(clf_s)),
        'positives':int(yc.sum()),
        'negatives':int((1-yc).sum())
    })
clf_results_df=pd.DataFrame(clf_results).sort_values('roc_auc', ascending=False)
clf_results_df.to_csv(OUT/'vc_scout_tier_classifier_diagnostic_final.csv', index=False)

# summaries
audit_rows = [
    {'metric':'Expanded rows audited','value':int(len(df)),'note':'Rows in startup_master.csv'},
    {'metric':'Rows with valuation','value':int(df['valuation_b_latest'].notna().sum()),'note':'Valuation coverage is mostly unicorn/current/former only'},
    {'metric':'Rows with funding','value':int(df['funding_original_usd'].notna().sum()),'note':'Funding coverage varies by source and tier'},
    {'metric':'Unicorn rows with valuation and funding checked','value':int(val_fund.sum()),'note':'Population eligible for funding-unit audit'},
    {'metric':'Unit-suspect unicorn funding rows corrected for analysis','value':int(unit_suspect.sum()),'note':'Working correction divides original funding by 1,000; raw value is preserved'},
    {'metric':'Rows with funding > valuation after correction','value':int(post_bad.sum()),'note':'Should be separately reviewed if nonzero'},
    {'metric':'Form D Q2 2026 rows','value':int(len(fd)),'note':'Separate market context table'},
    {'metric':'Form D mega raises >= $100M','value':mega_total,'note':'Large Q2 2026 raises in raw Form D file'},
    {'metric':'Mega raises in likely non-startup categories','value':mega_nonstartup,'note':'Finance/real estate/insurance/investing categories'},
    {'metric':'Mega-raise dollars in likely non-startup categories','value':mega_dollar_share_nonstartup,'note':'Share of dollars, not row count'}
]
audit_df = pd.DataFrame(audit_rows)
audit_df.to_csv(OUT/'vc_scout_audit_summary_final.csv', index=False)

tier_summary = df.groupby('tier').agg(
    rows=('company','size'),
    valuation_rows=('valuation_b_latest',lambda s:s.notna().sum()),
    funding_rows=('funding_original_usd',lambda s:s.notna().sum()),
    countries=('country',lambda s:s.nunique(dropna=True)),
    median_valuation_b=('valuation_b_latest','median'),
    median_funding_audited_b=('funding_audited_usd', lambda s: np.nanmedian(s)/1e9)
).reset_index()
tier_summary.to_csv(OUT/'vc_scout_tier_summary_final.csv', index=False)

hypotheses = [
    {'hypothesis':'H1: 2021 is a distinct market regime','status':'Supported descriptively/statistically','evidence':f"2021 is the largest single dated cohort in the expanded current-unicorn list ({int((u_dates['era']=='2021').sum())} rows); era differences in valuation and funding are statistically significant; sector mix differs by era.", 'planned_followup':'Bring in external VC funding/interest-rate data only if the final project needs causal COVID interpretation.'},
    {'hypothesis':'H2: Funding predicts valuation with diminishing returns','status':'Supported','evidence':f"Audited benchmark champion test R2={res.iloc[0]['test_r2']:.2f}; no-funding stress test R2={no_funding_result['test_r2']:.2f}; log-log funding elasticity ~= {funding_elasticity:.2f}.", 'planned_followup':'Use benchmark residuals rather than raw valuations to spot capital-efficient outperformance.'},
    {'hypothesis':'H3: Sector/geography add signal beyond funding','status':'Partially supported','evidence':'Industry, country, and continent residual tables show directional variation, but several medians are muted and small categories require confidence flags.', 'planned_followup':'Use sample-size penalties and confidence bands before turning residuals into rankings.'},
    {'hypothesis':'H4: Expanded controls solve survivorship bias','status':'Disproven / only partially solved','evidence':'The 75k-row master adds comparison tiers, but sources are mixed across time and valuation coverage is only 1,829 rows.', 'planned_followup':'Use expanded data for diagnostic tier comparisons, not causal startup-success prediction.'},
    {'hypothesis':'H5: Investor count is enough for investor network effects','status':'Not proven','evidence':'Investor count is a weak proxy for investor quality, timing, and co-investor networks.', 'planned_followup':'Add top-fund flags and co-investor network features in final implementation.'}
]
hyp_df = pd.DataFrame(hypotheses)
hyp_df.to_csv(OUT/'vc_scout_hypothesis_summary_final.csv', index=False)

# ----------------------------
# Charts
# ----------------------------
plt.rcParams.update({'font.size':9, 'font.family':'DejaVu Sans'})
BG='#0E1320'; CARD='#111A2B'; INK='#F4F7FB'; MUTED='#A8B3C5'; CYAN='#45D4FF'; GREEN='#7EE787'; AMBER='#FFB84D'; RED='#FF6B6B'; PURPLE='#B58CFF'; GRID='#2A3958'

def savefig(name, fig=None):
    fig = fig or plt.gcf()
    fig.patch.set_facecolor(BG)
    for ax in fig.axes:
        ax.set_facecolor(CARD)
        ax.tick_params(colors=MUTED)
        ax.xaxis.label.set_color(MUTED); ax.yaxis.label.set_color(MUTED); ax.title.set_color(INK)
        for sp in ax.spines.values(): sp.set_color(GRID)
        ax.grid(True, color=GRID, alpha=0.35, linewidth=0.6)
    fig.tight_layout()
    fig.savefig(OUT/name, dpi=220, facecolor=BG, bbox_inches='tight')
    plt.close(fig)

# coverage audit chart
coverage = pd.DataFrame({
    'metric':['valuation coverage','funding coverage','unit-suspect unicorn funding','noisy Form D mega dollars'],
    'pct':[df['valuation_b_latest'].notna().mean()*100, df['funding_original_usd'].notna().mean()*100, unit_suspect.sum()/max(val_fund.sum(),1)*100, mega_dollar_share_nonstartup*100],
    'color':[PURPLE,CYAN,AMBER,RED]
})
fig,ax=plt.subplots(figsize=(6.2,3.8))
ypos=np.arange(len(coverage))
ax.barh(ypos, coverage['pct'], color=coverage['color'])
ax.set_yticks(ypos); ax.set_yticklabels(coverage['metric'], color=INK)
ax.set_xlim(0,100); ax.set_xlabel('% of relevant rows/dollars')
ax.set_title('Data audit: coverage and risk indicators')
for i,v in enumerate(coverage['pct']): ax.text(v+1,i,f'{v:.1f}%',va='center',color=INK,fontsize=9)
savefig('audit_coverage_final.png', fig)

# era count chart
fig,ax=plt.subplots(figsize=(7.0,3.8))
yc=year_counts[(year_counts['unicorn_year']>=2014) & (year_counts['unicorn_year']<=2026)].copy()
colors=[AMBER if int(y)==2021 else CYAN for y in yc['unicorn_year']]
ax.bar(yc['unicorn_year'].astype(int).astype(str), yc['count'], color=colors)
ax.set_title('2021 remains the largest dated unicorn cohort')
ax.set_xlabel('Year joined unicorn list'); ax.set_ylabel('Current/former unicorn rows')
ax.tick_params(axis='x', rotation=45)
for _,r in yc.iterrows():
    if int(r['unicorn_year'])==2021:
        ax.text(str(int(r['unicorn_year'])), r['count']+10, str(int(r['count'])), color=INK, ha='center', fontsize=10, fontweight='bold')
savefig('era_year_counts_final.png', fig)

# era medians chart
fig,ax=plt.subplots(figsize=(6.5,3.6))
plot=era_summary.set_index('era').loc[era_order]
x=np.arange(len(plot)); w=.32
ax.bar(x-w/2, plot['median_valuation_b'], width=w, label='Median valuation ($B)', color=GREEN)
ax.bar(x+w/2, plot['median_funding_b'], width=w, label='Median funding ($B)', color=CYAN)
ax.set_xticks(x); ax.set_xticklabels(era_order)
ax.set_title('Era comparison: valuation and funding medians shift')
ax.legend(frameon=False, labelcolor=MUTED, fontsize=8)
savefig('era_medians_final.png', fig)

# model comparison chart
fig,ax=plt.subplots(figsize=(7.0,3.8))
plot=res.sort_values('test_r2')
ypos=np.arange(len(plot))
ax.barh(ypos-0.18, plot['cv_r2_mean'], height=.32, label='CV R²', color=PURPLE)
ax.barh(ypos+0.18, plot['test_r2'], height=.32, label='Test R²', color=GREEN)
ax.set_yticks(ypos); ax.set_yticklabels(plot['model'], color=INK)
ax.set_xlim(0, max(plot['test_r2'].max(), plot['cv_r2_mean'].max())+.12)
ax.set_title('Audited valuation benchmark: modest but usable signal')
ax.legend(frameon=False, labelcolor=MUTED, fontsize=8)
for i,v in enumerate(plot['test_r2']): ax.text(v+.01,i+.18,f'{v:.2f}',va='center',color=INK,fontsize=8)
savefig('model_results_final.png', fig)

# funding elasticity scatter
sample=model_df.sample(n=min(len(model_df), 900), random_state=17)
fig,ax=plt.subplots(figsize=(6.7,3.8))
ax.scatter(sample['funding_audited_usd']/1e9, sample['valuation_b_latest'], s=14, alpha=0.5, color=CYAN, edgecolors='none')
ax.set_xscale('log'); ax.set_yscale('log')
ax.set_xlabel('Audited funding ($B, log scale)'); ax.set_ylabel('Valuation ($B, log scale)')
ax.set_title(f'Funding matters, but sub-linearly (elasticity ~= {funding_elasticity:.2f})')
savefig('funding_elasticity_final.png', fig)

# residual industry chart
fig,ax=plt.subplots(figsize=(7.2,3.9))
ind=industry_resid.head(8).sort_values('avg_residual_ln')
colors=[GREEN if v>=0 else RED for v in ind['avg_residual_ln']]
ax.barh(ind['industry_group'], ind['avg_residual_ln'], color=colors)
ax.axvline(0, color=MUTED, lw=1)
ax.set_title('Benchmark outperformance by industry')
ax.set_xlabel('Average residual ln(actual valuation / expected valuation)')
for i,(v,n) in enumerate(zip(ind['avg_residual_ln'],ind['n'])):
    ax.text(v+0.01 if v>=0 else v-0.01, i, f'n={int(n)}', va='center', ha='left' if v>=0 else 'right', color=INK, fontsize=8)
savefig('industry_residuals_final.png', fig)

# residual country chart
fig,ax=plt.subplots(figsize=(7.2,3.9))
cty=country_resid.head(8).sort_values('avg_residual_ln')
colors=[GREEN if v>=0 else RED for v in cty['avg_residual_ln']]
ax.barh(cty['country'], cty['avg_residual_ln'], color=colors)
ax.axvline(0, color=MUTED, lw=1)
ax.set_title('Benchmark outperformance by country')
ax.set_xlabel('Average residual ln(actual valuation / expected valuation)')
for i,(v,n) in enumerate(zip(cty['avg_residual_ln'],cty['n'])):
    ax.text(v+0.01 if v>=0 else v-0.01, i, f'n={int(n)}', va='center', ha='left' if v>=0 else 'right', color=INK, fontsize=8)
savefig('country_residuals_final.png', fig)

# classifier chart
fig,ax=plt.subplots(figsize=(6.8,3.6))
plot=clf_results_df.copy()
metrics=['roc_auc','balanced_accuracy','avg_precision']; x=np.arange(len(plot)); width=.22
cols=[CYAN,GREEN,PURPLE]
labels=['ROC AUC','Balanced accuracy','Average precision']
for j,(m,label) in enumerate(zip(metrics, labels)):
    ax.bar(x+(j-1)*width, plot[m], width, label=label, color=cols[j])
ax.set_xticks(x); ax.set_xticklabels(plot['model'], rotation=10, ha='right')
ax.set_ylim(0,1.14)
ax.set_title('Expanded-tier classifier: high diagnostic accuracy, high bias risk', pad=22)
leg=ax.legend(frameon=False, fontsize=8.2, ncol=3, loc='upper center', bbox_to_anchor=(0.5,1.08), borderaxespad=0.0)
for txt in leg.get_texts():
    txt.set_color(INK)
ax.margins(x=0.04)
savefig('tier_classifier_final.png', fig)

# Write source of truth
source_truth = {
    'inputs': {
        'startup_master.csv_rows': int(len(sm)),
        'formd_2026q2_raises.csv_rows': int(len(fd)),
        'build_summary': summary
    },
    'audit_metrics': audit_rows,
    'era_summary': era_summary.to_dict(orient='records'),
    'era_tests': {
        'valuation_kruskal_p': kruskal_p('valuation_b_latest'),
        'funding_kruskal_p': kruskal_p('funding_audited_usd'),
        'years_to_unicorn_kruskal_p': kruskal_p('years_to_unicorn'),
        'sector_mix_chi_square_p': chi_sector_p
    },
    'valuation_model': {
        'rows': int(len(model_df)),
        'champion': champion_name,
        'model_results': res.to_dict(orient='records'),
        'funding_elasticity': funding_elasticity,
        'no_funding_stress_test': no_funding_result,
        'permutation_importance': perm_df.to_dict(orient='records')
    },
    'expanded_tier_classifier_diagnostic': clf_results_df.to_dict(orient='records'),
    'hypotheses': hypotheses,
    'top_industry_residuals': industry_resid.head(10).to_dict(orient='records'),
    'top_country_residuals': country_resid.head(10).to_dict(orient='records')
}
(OUT/'vc_scout_source_of_truth_final.json').write_text(json.dumps(source_truth, indent=2))

# package audit trail
zip_path = DATA/'vc_scout_revised_results_audit_trail_final.zip'
with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for file in OUT.glob('*.csv'):
        z.write(file, arcname=file.name)
    z.write(OUT/'vc_scout_source_of_truth_final.json', arcname='vc_scout_source_of_truth_final.json')
    z.write(Path(__file__), arcname='vc_scout_final_analysis.py')

print(json.dumps({
    'assets_dir': str(OUT),
    'zip': str(zip_path),
    'champion': champion_name,
    'test_r2': float(res.iloc[0]['test_r2']),
    'funding_elasticity': funding_elasticity,
    'no_funding_r2': no_funding_result['test_r2'],
    'unit_suspect_corrected': int(unit_suspect.sum()),
    'era_summary': era_summary.to_dict(orient='records'),
    'formd_mega_nonstartup_share': mega_dollar_share_nonstartup
}, indent=2))
