# -*- coding: utf-8 -*-
# Author: Izaak Neutelings (2017)
# Moved from TauFW.Plotter.plot.string by Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Labels of plots: LaTeX titles of variables (makelatex, maketitle), file-safe names (makefilename,
makehistname), legend text length (estimatelen) and glob/regex matching of names (match).

Moved verbatim from TauFW.Plotter.plot.string; the selection-string helpers (joincuts, invertcharge, ...) stayed
there, and the Plotter imports these names from here."""
import re
from TauFW.Utilities.Drawing import LOG
from TauFW.Utilities.Drawing._internal.legacy_helpers import unpacklistargs, ensurelist, islist

var_dict = { # predefined variable titles
    'njets':     "Number of jets",          'njets20':  "Number of jets (pt>20 GeV)",          'njets50':  "Number of jets (pt>50 GeV)",
    'nfjets':    "Number of forward jets",  'nfjets20': "Number of forward jets (pt>20 GeV)",  'nfjets50': "Number of forward jets (pt>50 GeV)",
    'ncjets':    "Number of central jets",  'ncjets20': "Number of central jets (pt>20 GeV)",  'ncjets50': "Number of central jets (pt>50 GeV)",
    'nbtag':     "Number of b tagged jets", 'nbtag20':  "Number of b tagged jets (pt>20 GeV)", 'nbtag50':  "Number of b tagged jets (pt>50 GeV)",
    'jpt_1':     "Leading jet pt",          'jpt_2':    "Subleading jet pt",
    'bpt_1':     "Leading b jet pt",        'bpt_2':    "Subleading b jet pt",
    'jeta_1':    "Leading jet eta",         'jeta_2':   "Subleading jet eta",
    'beta_1':    "Leading b jet eta",       'beta_2':   "Subleading b jet eta",
    'jphi_1':    "Leading jet phi",         'bphi_1':   "Subleading jet phi",
    'jphi_2':    "Leading b jet phi",       'bphi_2':   "Subleading b jet phi",
    'met':       "p_{T}^{miss}",            'genmet':   "Gen. p_{T}^{miss}",
    'metphi':    "MET phi",                 'genmetphi':"Gen. MET phi",
    'pt_1':      "Lepton pt",               'pt_2':     "tau_h pt",
    'eta_1':     "Lepton eta",              'eta_2':    "tau_h eta",
    'm_vis':     "m_{#lower[-0.1]{vis}}",   'mvis':     "m_{#lower[-0.1]{vis}}",
    'mt_1':      "m_t(l,MET)",              'mt_2':     "m_t(tau,MET)",
    'dzeta':     "D_{zeta}",                'pt_1+pt_2+jpt_1':     "S_{#lower[-0.1]{T}}^{#lower[0.1]{MET}}",
    'pzetavis':  "p_{zeta}^{vis}",          'pt_1+pt_2+jpt_1+met': "S_{#lower[-0.1]{T}}^{#lower[0.1]{MET}}",
    'pzetamiss': "p_{zeta}^{miss}",         'stmet':    "S_{T}^{MET}",
    'DM0':       "h^{#pm}",                 'STMET':    "S_{T}^{MET}",
    'DM1':       "h^{#pm}h^{0}",
    'DM10':      "h^{#pm}h^{#mp}h^{#pm}",
    'DM11':      "h^{#pm}h^{#mp}h^{#pm}h^{0}",
}
var_dict_sorted = sorted(var_dict,key=lambda x: len(x),reverse=True) # sort keys by length once


funcexpr = re.compile(r"(\w+)\(([^,]+),([^,]+)\)")
def makelatex(string,**kwargs):
  """Convert patterns in a string to LaTeX format."""
  global var_dict_sorted
  verbosity = LOG.getverbosity(kwargs)#+4
  if not isinstance(string,str) or not string:
    return string
  if string and string[0]=='{' and string[-1]=='}':
    return string[1:-1]
  units  = kwargs.get('units', True  )
  split  = kwargs.get('split', False )
  GeV    = False
  cm     = False
  oldstr = string
  
  # PREDEFINED
  if len(var_dict_sorted)!=len(var_dict): # sort again
    var_dict_sorted = sorted(var_dict,key=lambda x: len(x),reverse=True)
  for var in var_dict_sorted:
    if var in string:
      LOG.verb("makelatex: Found var %r in string %r => replace with %r"%(var,string,var_dict[var]),verbosity,2)
      string = string.replace(var,var_dict[var])
      #string = re.sub(r"\b%s\b"%var,var_dict[var],string,re.IGNORECASE)
      break
  
  # SPLIT LINE
  if split:
    while '\n' in string:
      string = "#splitline{%s}"%(string.replace('\n','}{',1))
    if 'splitline' not in string and len(string)>30:
      part1 = string[:len(string)/2]
      part2 = string[len(string)/2:]
      if ' ' in part2:
        string = "#splitline{"+part1+part2.replace(' ','}{',1)+"}"
      elif ' ' in part1:
        i = part1.rfind(' ')
        string = "#splitline{"+string[:i]+'}{'+string[i+1:]+"}"
  
  # REPLACE PATTERNS (RECURSIVELY)
  match = funcexpr.match(string) # for min(), max(), ...
  if ' / ' in string:
    kwargs['units'] = False
    string = ' / '.join(makelatex(s,**kwargs) for s in string.split(' / '))
  elif match:
    kwargs['units'] = False
    func   = makelatex(match.group(1),**kwargs)
    arg1   = makelatex(match.group(2),**kwargs)
    arg2   = makelatex(match.group(3),**kwargs)
    old    = "%s(%s,%s)"%(match.group(1),match.group(2),match.group(3))
    new    = "%s(%s,%s)"%(func,arg1,arg2)
    string = string.replace(old,new)
    #print ">>> %r -> %r, %r -> %r, %r -> %r, %r"%(match.group(2),arg1,match.group(3),arg2,old,new,string)
  elif '+' in string:
    kwargs['units'] = False
    string = '+'.join(makelatex(s,**kwargs) for s in string.split('+'))
  else:
    strlow = string.lower().strip()
    if not strlow:
      return string
    if "p_" in strlow:
      string = re.sub(r"(?<!i)(p)_([^{}()|<>=\ ]+)",r"\1_{\2}",string,flags=re.IGNORECASE).replace('{t}','{T}') ##lower[-0.2]{T}
      GeV    = True
    if re.search(r"(?<!le)(?<!byphoton)(?<!dee)(?<!prom)pt(?!weight)",strlow): # pt
      string = re.sub(r"(?<!k)(?<!Dee)(?<!OverTau)(p)[tT]_([^{}()|<>=_\ ]+)",r"\1_{T}^{\2}",string,flags=re.IGNORECASE)
      string = re.sub(r"\b(?<!Dee)(p)[tT]\b",r"\1_{T}",string,flags=re.IGNORECASE)
      GeV    = True
    if strlow=="mt":
      string = re.sub(r"(m)(t)(?![\w,:])",r"\1_{T}",string,flags=re.IGNORECASE)
      GeV    = True
    elif "m_" in strlow:
      string = re.sub(r"(?<!u)(m)_([^{}()|<>=\ \^]+)",r"\1_{\2}",string,flags=re.IGNORECASE).replace('{t}','{T}')
      GeV    = True
    elif "mt" in strlow:
      if "mt_" in strlow:
        string = re.sub(r"(m)t_([^{}()|<>=\ ]+)",r"\1_{T}^{\2}",string,flags=re.IGNORECASE)
      else: # "naked" mt
        string = re.sub(r"(?<!\w)(m)t(?![\w,:])",r"\1_{T}",string,flags=re.IGNORECASE)
      GeV    = True
    if re.search(r"(?<!weig)(?<!daug)ht(?!au)",strlow): # HT
      string = re.sub(r"\b(h)t\b",r"\1_{T}",string,flags=re.IGNORECASE)
      GeV    = True
    if strlow[0]=='s' and 't' in strlow[1:3] and 'std' not in strlow[:3] and 'tw' not in strlow[2:5] and 'chan' not in strlow[2:10]: # scalar sum pT
      string = re.sub(r"s_?t(?!at)(?![ _-]t[Wc-])",r"S_{T}",string,flags=re.IGNORECASE)
      string = re.sub(r"met",r"^{MET}",string,flags=re.IGNORECASE)
      GeV    = True
    if " d_" in strlow:
      string = re.sub(r"(\ d)_([^{}()\|<>=\ ]+)",r"\1_{\2}",string,flags=re.IGNORECASE)
      cm     = True
    if "deltar_" in strlow:
      string = re.sub(r"(?<!\#)deltar_([^{}()|<>=\ ]+)",r"#DeltaR_{\1}",string,flags=re.IGNORECASE)
    elif "deltar" in strlow:
      string = re.sub(r"(?<!\#)deltar",r"#DeltaR",string,flags=re.IGNORECASE)
    elif "dr_" in strlow:
      string = re.sub(r"(?<!\w)dr_([^{}()|<>=\ ]+)",r"#DeltaR_{\1}",string,flags=re.IGNORECASE)
    elif "dr" in strlow:
      string = re.sub(r"(?<![a-z])dr(?![a-z])",r"#DeltaR",string,flags=re.IGNORECASE)
    if "chi" in strlow:
      string = re.sub(r"(?<!#)chi(?!ng)",r"#chi",string,flags=re.IGNORECASE)
      string = re.sub(r"chi_([^{}()^|<>=\ ]+)",r"chi_{\1}",string,flags=re.IGNORECASE)
    if "phi" in strlow:
      if "dphi" in strlow:
        string = string.replace("dphi","#Delta#phi")
      else:
        string = string.replace("phi","#phi")
      string = re.sub(r"phi_([^{}()|<>=\ ]+)",r"phi_{\1}",string,flags=re.IGNORECASE)
    if "zeta" in strlow and "#zeta" not in strlow:
      if "Dzeta" in string:
        string = string.replace("Dzeta","D_{zeta}")
        GeV    = True
      if "zeta_" in strlow:
        string = re.sub(r"(?<!#)(zeta)_([^{}()|<>=\ ]+)",r"#\1_{\2}",string,flags=re.IGNORECASE)
      else:
        string = re.sub(r"(?<!#)(zeta)",r"#\1",string,flags=re.IGNORECASE)
      GeV      = True
    if "eta" in strlow: #and "#eta" not in strlow and "#zeta" not in strlow and "deta" not in strlow:
      string = string.replace("deta","#Deltaeta")
      string = re.sub(r"(?<!\#[Bbz])eta(?!u)",r"#eta",string)
      string = re.sub(r"eta_([^{}()|<>=\ ]+)",r"eta_{\1}",string)
    if "tau" in strlow:
      #string = re.sub(r"(?<!^)tau(?!\ )",r"#tau",string,re.IGNORECASE)
      string = re.sub(r"(?<!Deep|Over|ToMu)(?<!To)(?<!ToTau)(?<!#)tau(?!filter)",r"#tau",string,flags=re.IGNORECASE)
      #string = re.sub(r" #tau ",r" tau ",string,flags=re.IGNORECASE)
      #string = re.sub(r"^#tau ",r"tau ",string,flags=re.IGNORECASE)
      string = re.sub(r"tau_([^{}()^|<>=\ ]+)",r"tau_{\1}",string,flags=re.IGNORECASE)
      string = re.sub(r"#tauh",r"#tau_{#lower[-0.2]{h}}",string,flags=re.IGNORECASE)
    if "abs(" in string and ")" in string:
      string = re.sub(r"abs\(([^)]+)\)",r"|\1|",string)
      #string = string.replace("abs(","|").replace(")","") + "|" # TODO: split at next space
    if "mu" in strlow:
      string = re.sub(r"(?<!VS)mu(?![lo])(?!taufilter)",r"#mu",string)
      #string = string.replace("mu","#mu").replace("Mu","#mu")
      #string = string.replace("si#mulation","simulation")
    if "nu" in strlow:
      string = re.sub(r"(?<!mi)nu(?![pm])",r"#nu",string)
    if "ttbar" in strlow:
      string = re.sub(r"ttbar","t#bar{t}",string,flags=re.IGNORECASE)
    if "npv" in strlow:
      string = re.sub(r"npvs?","Number of primary vertices",string)
    if '->' in string:
      string = string.replace('->','#rightarrow')
    if '=' in string:
      string = string.replace(">=","#geq").replace("<=","#leq")
    string = string.replace('##','#')
  
  # UNITS
  if isinstance(units,str):
    if re.search(r"[(\[].*[)\]]",units):
      string += " "+units.strip()
    else:
      string += " [%s]"%units.strip()
  elif units and not '/' in string: # set unit automatically (except for ratio)
    if GeV or "mass" in string or "p_{T}" in string or "S_{T}" in string or (any(m in string.lower() for m in ["met","p_{t}^{miss}"]) and not any(p in string for p in ["phi","parameter"])):
      if "GeV" not in string:
        string += " [GeV]"
      if cm:
        LOG.warn("makelatex: Flagged units are both GeV and cm!")
    elif cm and 'cm' not in string: #or 'd_' in string
      string += " [cm]"
  if (verbosity>=2 and string!=oldstr) or verbosity>=3:
    print(">>> makelatex: %r -> %r"%(oldstr,string))
  return string
  

def maketitle(title,**kwargs):
  """Make header with LaTeX."""
  kwargs.update({'units':False, 'split':False})
  title = makelatex(title,**kwargs)
  return title
  

def makehistname(*strings,**kwargs):
  """Use given strings to make an unique and valid histogram name that is filename safe."""
  kwargs.setdefault('dots',False)
  #hname = '_'.join(getobjname(s).strip('_') for s in strings) #.replace(' ','_')
  hname = makefilename(*strings,**kwargs)
  hname = hname.replace('[','').replace(']','').replace('*','x').replace('.', 'p')
  return hname
  

def makefilename(*strings,**kwargs):
  """Make string filename safe by replacing inconvenient characters."""
  fname = '_'.join(getobjname(s).strip('_') for s in strings)
  fname = re.sub(r"(\d+)\.(\d+)",r"\1p\2",fname)
  if 'abs(' in fname:
    fname = re.sub(r"abs\(([^\)]*)\)",r"abs\1",fname).replace('eta_2','eta')
  if 'm_t' in fname.lower():
    fname = re.sub(r"(?<![a-zA-Z])m_[tT](?!au)",r"mt",fname)
  if 'GeV' in fname:
    fname = re.sub(r"(?<![a-zA-Z])GeV","",fname)
  fname = fname.replace(" and ",'-').replace(',','-').replace('+','-').replace('::','-').replace(':','-').replace(
                        '(','-').replace(')','').replace('{','').replace('}','').replace(
                        '\n','-').replace('\\','').replace('/','-').replace(' ','').replace('__','_').replace('--','-').replace(
                        '||','OR').replace('&&','AND').replace('|','').replace('&','').replace('#','').replace('!','not').replace(
                        #'pt_mu','pt').replace('m_T','mt').replace('GeV','').replace('anti-iso',"antiIso").replace(
                        '>=',"geq").replace('<=',"leq").replace('>',"gt").replace('<',"lt").replace('==','eq').replace("=","eq")
  if not kwargs.get('dots',True): # replace periods
    fname = fname.replace('.','p')
  #if 'm_t' in string.lower:
  #  string = re.sub(r"(?<!u)(m)_([^{}\(\)<>=\ ]+)",r"\1_{\2}",string,re.IGNORECASE).replace('{t}','{T}')
  #if "m_" in string.lower():
  #    string = re.sub(r"(?<!u)(m)_([^{}\(\)<>=\ ]+)",r"\1_{\2}",string,re.IGNORECASE).replace('{t}','{T}')
  #if not (".png" in name or ".pdf" in name or ".jpg" in name): name += kwargs.get('ext',".png")
  return fname

  
def getobjname(string,**kwargs):
  """Make sure returned object is a string."""
  if hasattr(string,"filename"):
    return string.filename
  elif hasattr(string,"name"):
    return string.name
  elif hasattr(string,"GetName"):
    return string.GetName()
  return string
  

symregx = re.compile(r"#[a-zA-Z]+") # regular expression for TLatex symbols
cmdregx = re.compile(r"#[a-zA-Z]+\[[-\d\.]+\]") # regular expression for TLatex commands
def estimatelen(*strings):
  """Estimate maximum length of list of strings."""
  strings = unpacklistargs(*strings)
  maxlen  = 0
  replace = [
    ('{',''),('}',''),('_',''),('^',''),('#','')
  ]
  for string in strings:
    if not string: continue
    if '\n' in string:
      strlen = estimatelen(string.split('\n'))
    else:
      string = cmdregx.sub('',string)
      string = symregx.sub('x',string)
      for old, new in replace:
        string = string.replace(old,new)
      strlen = len(string)
    if strlen>maxlen:
      maxlen = strlen
  return maxlen
  

def match(terms, labels, **kwargs):
  """Match given search terms (strings) to some given list of labels."""
  verbosity = LOG.getverbosity(kwargs)
  terms     = ensurelist(terms, nonzero=True) # search terms / filters
  labels    = ensurelist(labels,nonzero=True) # labels to match to
  found     = True
  regex     = kwargs.get('regex', False ) # use regexpr patterns (instead of glob)
  incl      = kwargs.get('incl',  True  ) # match at least one term; if incl=False ("exclusive"), match every term
  start     = kwargs.get('start', False ) # match only beginning of string
  LOG.verb("match: compare labels=%s -> searchterms=%s (incl=%s,regex=%s)"%(labels,terms,incl,regex),verbosity,3)
  if not terms:
    return False
  for i, searchterm in enumerate(terms):
    if not searchterm: continue
    if not regex: # convert glob to regexp
      #fnmatch.translate( '*.foo' )
      #searchterm = re.sub(r"(?<!\\)\+",r"\+",searchterm)   # replace + with \+
      #searchterm = re.sub(r"([^\.])\*",r"\1.*",searchterm) # replace * with .*
      searchterm = re.escape(searchterm)
      searchterm = searchterm.replace(r'\?','.').replace(r'\*','.*?').replace(r'\^','^'
                            ).replace(r'\[','[').replace(r'\]',']') #.replace(r'\_','_')
    if start and not searchterm.startswith('^'):
      searchterm = '^'+searchterm
    terms[i] = searchterm
  if incl: # inclusive: match only one search term
    for searchterm in terms:
      for label in labels:
        matches = re.findall(searchterm,label)
        if matches:
          LOG.verb("  matched %r -> %r; return True"%(label,searchterm),verbosity,3)
          return True # one search terms is matched
        else:
          LOG.verb("  not matched %r -> %r"%(label,searchterm),verbosity,3)
    return False # no search term was matched
  else: # exclusive: match all search terms
    for searchterm in terms:
      for label in labels:
        matches = re.findall(searchterm,label)
        if matches:
          LOG.verb("  matched %r -> %r"%(label,searchterm),verbosity,3)
          break
        else:
          LOG.verb("  not matched %r -> %r"%(label,searchterm),verbosity,3)
      else:
        return False # this search terms was not matched
    return True # all search terms were matched
  

