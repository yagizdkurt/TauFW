#! /usr/bin/env python3
"""Load DM-binned tau SFs from tau_sf/ for a given year (-y, default 2025) and produce
a combined correctionlib JSON with TES + TauID, both carrying the per-(DM, pT-bin)
uncorrelated systematics.

Variants:
  --variant uncorr (default): per-WP JSONs ..._<year>_VSjet*_VSele*.json
                              TES + TauID both per (DM, pT bin).
  --variant corr            : per-WP JSONs ..._<year>_corrTES_VSjet*_VSele*.json
                              TES per-DM only (1 inclusive pT bin), TauID per (DM, pT).
  --variant fullcorr        : per-WP JSONs ..._<year>_fullcorr_VSjet*_VSele*.json
                              TES per-DM only (1 inclusive pT bin); TauID per (DM, pT) is the
                              *effective* SF computed from common POI × (1 + 0.10·θ̂_pt).
"""
import os, sys, json, argparse
from tau_tid_2024 import makecorr_tid, schema, JSONEncoder

HERE       = os.path.dirname(os.path.abspath(__file__))
SF_DIR     = os.path.join(HERE, 'tau_sf')
VSJET_WPS  = ['VVLoose','VLoose','Loose','Medium','Tight','VTight']
VSE_WPS    = ['VVLoose','Tight']
DMS        = [0,1,10,11]
LABEL      = 'DeepTau2018v2p5'        # filename tagger component (set from --config tagger)
TID_LABEL  = 'DeepTau2018v2p5VSjet'   # correctionlib id label (set from --config tagger)
PT_BINS    = [20.0,40.0,60.0,200.0]  # 3 pT bins for TauID (and TES uncorr)
TES_CORR_BINS = [20.0, 200.0]        # 1 inclusive bin for corrTES TES


def find_dm_node(node):
  """Recursively locate the DM-categorized node in a correctionlib JSON tree."""
  if isinstance(node, dict):
    if node.get('nodetype')=='category' and node.get('input')=='DM':
      return node
    for item in node.get('content',[]):
      r = find_dm_node(item)
      if r is not None: return r
    if 'value' in node:
      r = find_dm_node(node['value'])
      if r is not None: return r
  elif isinstance(node, list):
    for item in node:
      r = find_dm_node(item)
      if r is not None: return r
  return None


def extract_sfs(filepath):
  """Return {dm: [(nom, errup, errdown) per pT bin]} from one 2025 SF JSON."""
  with open(filepath) as f:
    data = json.load(f)
  dm_node = find_dm_node(data['corrections'][0]['data'])
  if dm_node is None:
    raise RuntimeError(f"No DM-categorized node in {filepath}")
  out = {}
  for entry in dm_node['content']:
    syst_vals = {se['key']: se['value']['content'] for se in entry['value']['content']}
    nom  = syst_vals['nom']
    up   = syst_vals['up']
    down = syst_vals['down']
    out[entry['key']] = [(nom[i], up[i]-nom[i], nom[i]-down[i]) for i in range(len(nom))]
  return out


def load_per_wp(prefix, year='2025', variant='uncorr'):
  """Build dmsfs[wp_VSjet][wp_VSe][dm] = [(nom, errup, errdown) per pT bin] from
     files like {prefix}_DeepTau2018v2p5_{year}[_<variant>]_VSjet{X}_VSele{Y}.json.

     Only WPs with files on disk are included — partial WP coverage works."""
  suffix = {'corr': '_corrTES', 'fullcorr': '_fullcorr'}.get(variant, '')
  dmsfs = {}
  for wjet in VSJET_WPS:
    for wse in VSE_WPS:
      fname = os.path.join(SF_DIR,
        f"{prefix}_{LABEL}_{year}{suffix}_VSjet{wjet}_VSele{wse}.json")
      if not os.path.exists(fname):
        print(f">>> WARNING: missing {fname}")
        continue
      dmsfs.setdefault(wjet, {})[wse] = extract_sfs(fname)
  return dmsfs


def dm_average(dmsfs):
  """Collapse dmsfs[wp][wse][dm] -> ptsfs[wp][wse] by averaging across DMs per pT bin.
     Used for the 'pt' flag (no DM split); 2025 has no separate inclusive pT measurement."""
  ptsfs = {}
  for wjet, vd in dmsfs.items():
    ptsfs[wjet] = {}
    for wse, dd in vd.items():
      n_pt = len(next(iter(dd.values())))
      avg = []
      for i in range(n_pt):
        noms = [dd[d][i][0] for d in dd]
        ups  = [dd[d][i][1] for d in dd]
        dns  = [dd[d][i][2] for d in dd]
        avg.append((sum(noms)/len(noms), sum(ups)/len(ups), sum(dns)/len(dns)))
      ptsfs[wjet][wse] = avg
  return ptsfs


def build_correction(prefix, name, tid_label, info, output_desc, year='2025',
                     variant='uncorr', pt_bins=None):
  """Read per-WP files matching `prefix`, return a single schema.Correction."""
  dmsfs = load_per_wp(prefix, year=year, variant=variant)
  ptsfs = dm_average(dmsfs)
  bins  = pt_bins if pt_bins is not None else PT_BINS
  return makecorr_tid(
    ptsfs       = ptsfs,
    dmsfs       = dmsfs,
    Format      = 'Run3_May24',
    id          = tid_label,
    era         = year,
    wps_VSe     = VSE_WPS,
    dms         = DMS,
    bins        = bins,
    dmptbins    = bins,
    name        = name,
    info        = info,
    output_desc = output_desc,
    fname       = '',  # suppress per-correction write
    verb        = 0,
  )


def main():
  ap = argparse.ArgumentParser(description=__doc__)
  ap.add_argument('-y', '--year', default='2025',
                  help="era of the tau_sf/ input JSONs and output labels (default: %(default)s)")
  ap.add_argument('--variant', choices=['uncorr','corr','fullcorr'], default='uncorr',
                  help="uncorr: TES per (DM,pT); corr: TES per-DM; fullcorr: TES per-DM, TauID per (DM,pT) is effective SF")
  ap.add_argument('--out', default=None,
                  help="output JSON (default: data/tau/TauCorrections_<year>[_<variant>]_with_uncorrelated_systs.json)")
  ap.add_argument('-c', '--config', default=None,
                  help="fit config with a 'tagger' block (PNet/UParT). If omitted, DeepTau defaults are used.")
  ap.add_argument('--sf-dir', dest='sf_dir', default=None,
                  help="directory of the per-WP input JSONs (default: tau_sf/ next to this script)")
  args = ap.parse_args()

  year    = args.year
  variant = args.variant

  # Tagger-aware: derive label / id / VSjet WPs / DM list from the config (DeepTau default)
  global VSJET_WPS, DMS, LABEL, TID_LABEL, SF_DIR
  if args.sf_dir: # BUGS F17: was always tau_sf/ next to this script
    SF_DIR = args.sf_dir
  if args.config:
    import yaml
    with open(args.config) as _f:
      _setup = yaml.safe_load(_f)
    _tagger = _setup.get('tagger') or {}
    TID_LABEL = _tagger.get('id_label', TID_LABEL)
    LABEL     = TID_LABEL.replace('VSjet', '').rstrip('_') or 'DeepTau2018v2p5'
    if _tagger.get('vsjet', {}).get('wps'):
      VSJET_WPS = list(_tagger['vsjet']['wps'].keys())
    try:  # DM list from scanRegions: DM0->0, DM11->11, DMrest->-1
      _dms = []
      for _r in _setup["observables"]["m_vis"]["scanRegions"]:
        _d = _r.split('_')[0]
        if _d not in _dms:
          _dms.append(_d)
      DMS = [(-1 if _d == 'DMrest' else int(_d.replace('DM', ''))) for _d in _dms]
    except Exception:
      pass
    print(f">>> Tagger from config: id={TID_LABEL}, label={LABEL}, VSjet WPs={VSJET_WPS}, DMs={DMS}")
  # TES axis: 3 pT bins for uncorr, 1 inclusive bin for corr & fullcorr
  tes_pt_bins = TES_CORR_BINS if variant in ('corr', 'fullcorr') else PT_BINS

  print(f">>> Building TauID correction (year={year}, variant={variant})...")
  tid_corr = build_correction(
    prefix      = 'TauID_SF_dm',
    name        = 'TauID_SF',
    tid_label   = TID_LABEL,
    info        = f'Tau ID SFs for {TID_LABEL} in {year}',
    output_desc = 'Tau ID scale factor',
    year        = year,
    variant     = variant,
    pt_bins     = PT_BINS,
  )
  print(f">>> Building TES correction (year={year}, variant={variant})...")
  tes_corr = build_correction(
    prefix      = 'TauES_SF_dm',
    name        = 'TauEnergy_SF',
    tid_label   = TID_LABEL,
    info        = f"Tau Energy Scale corrections for {TID_LABEL} in {year} ({'correlated across pT per DM' if variant in ('corr', 'fullcorr') else 'per (DM, pT)'})",
    output_desc = 'Tau energy scale correction',
    year        = year,
    variant     = variant,
    pt_bins     = tes_pt_bins,
  )

  if args.out is None:
    outdir = os.path.join(HERE, 'data', 'tau')
    suffix = {'corr': '_corrTES', 'fullcorr': '_fullcorr'}.get(variant, '')
    label_tag = '' if LABEL == 'DeepTau2018v2p5' else f'_{LABEL}'  # keep DeepTau name unchanged
    args.out = os.path.join(outdir, f'TauCorrections{label_tag}_{year}{suffix}_with_uncorrelated_systs.json')
  os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
  cset = schema.CorrectionSet(
    schema_version = schema.VERSION,
    description    = f"Tau ES + ID SFs for {year} with per-(DM, pT-bin) uncorrelated systematic variations ({variant} variant)",
    corrections    = [tes_corr, tid_corr],
  )
  print(f">>> Writing {args.out}...")
  JSONEncoder.write(cset, args.out)


if __name__ == '__main__':
  main()
