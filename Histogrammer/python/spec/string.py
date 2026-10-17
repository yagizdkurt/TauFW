# -*- coding: utf-8 -*-
# Author: Izaak Neutelings (2017)
import re
from TauFW.Utilities.Drawing import LOG
from TauFW.common.tools.utils import unpacklistargs, ensurelist, islist
# Label helpers moved to the drawing library (2026); imported here so the selection helpers below and the
# modules that star-import this one keep the same names.
from TauFW.Utilities.Drawing.labels import var_dict, var_dict_sorted, funcexpr, makelatex, maketitle,\
                                          makehistname, makefilename, getobjname, symregx, cmdregx,\
                                          estimatelen, match
# Selection and weight expression helpers moved to TauFW.Utilities.Expressions (2026); imported here for the same
# reason as the label helpers.
from TauFW.Utilities.Expressions import getselstr, joinweights, joincuts, replacepattern, cleanbool


def undoshift(string):
  if islist(string):
    shiftless = [undoshift(s) for s in string]
  else:
    shiftless = re.sub(r"_[a-zA-Z]+([Uu]p|[Dd]own|[Nn]om)","",string)
  return shiftless
  

def shift(oldstr,shifttag,vars=["\w+"],**kwargs):
  """Shift all jet variable in a given string (e.g. to propagate JEC/JER).
  E.g. shift('jpt_1>50 && met<50','jesUp',['jpt_[12]','met']) -> 'pt_1>50 && jpt_1_jesUp>50 && met_jesUp<50'
  """
  verbosity = LOG.getverbosity(kwargs)
  newstr    = oldstr
  vars      = ensurelist(vars)
  if re.search(r"(Up|Down)",oldstr):
    print("shift: already shifts in %r"%(oldstr))
  if kwargs.get('us',True) and len(shifttag)>0 and shifttag[0]!='_': # ensure underscore in front
    shifttag = '_'+shifttag
  for oldvar in vars: # shift each jet/MET variable
    oldexp = r"\b("+oldvar+r")\b"
    newexp = r"\1%s"%(shifttag)
    newstr = re.sub(oldexp,newexp,newstr)
  if verbosity>=1:
    verbstr = ">>> shift: shift with %r shift: "%(newstr)
    if len(newstr)<20:
      verbstr += " %r -> %r"%(oldstr,newstr)
    elif len(newstr)<35:
      verbstr += "\n>>>   %r -> %r"%(oldstr,newstr)
    else:
      verbstr += "\n>>>   %r\n>>>   -> %r"%(oldstr,newstr)
    print(verbstr)
  return newstr
  

def shiftjme(oldstr,shifttag,jmevars=None,**kwargs):
  """Shift all jet variable in a given string (e.g. to propagate JEC/JER).
  E.g. shiftjme('jpt_1>50 && met<50','jesUp') -> 'pt_1>50 && jpt_1_jecUp>50 && met_jecUp<50'
  """
  if jmevars==None: # default jet/MET variables to shift
    jmevars   = [r'\w*mt_1',r'met(?!filter)'] if "unclusten" in shifttag.lower() else\
                [r'jpt_[12]',r'jeta_[12]',r'n\w*jets\w*',r'nc?btag\w*',r'\w*mt_1',r'met(?!filter)',r'dphi_ll_bj']
  return shift(oldstr,shifttag,jmevars,**kwargs)
  

def invertcharge(oldcuts,target='SS',**kwargs):
  """Help function to find, invert and replace charge selections."""
  verbosity = LOG.getverbosity(kwargs)
  oldcuts   = getselstr(oldcuts)
  newcuts   = oldcuts
  if oldcuts=="":
    newcuts = "q_1*q_2<0" if target=='OS' else "q_1*q_2>0" if target=='OS' else ""
  else:
    matchOS = re.findall(r"q_[12]\s*\*\s*q_[12]\s*<\s*0",oldcuts)
    matchSS = re.findall(r"q_[12]\s*\*\s*q_[12]\s*>\s*0",oldcuts)
    LOG.verbose("invertcharge: oldcuts=%r"%(oldcuts),verbosity,2)
    LOG.verbose("invertcharge: matchOS=%r, matchSS=%r"%(matchOS,matchSS),verbosity,2)
    if (len(matchOS)+len(matchSS))>1:
      LOG.warn('invertcharge: more than one charge match (%d OS, %d SS) in %r'%(len(matchOS),len(matchSS),oldcuts))
    if target=='OS':
      for match in matchSS: newcuts = oldcuts.replace(match,"q_1*q_2<0") # invert SS to OS
    elif target=='SS':
      for match in matchOS: newcuts = oldcuts.replace(match,"q_1*q_2>0") # invert OS to SS
    else:
      for match in matchOS: newcuts = oldcuts.replace(match,"") # REMOVE
      for match in matchSS: newcuts = oldcuts.replace(match,"") # REMOVE
    newcuts = cleanbool(newcuts)
  LOG.verbose('  %r\n>>>   -> %r %s\n>>>'%(oldcuts,newcuts,target),verbosity,2)
  return newcuts
  

###isopattern1 = re.compile(r"(?:idMVA\w+|pfRelIso0._all)_1 *!?[<=>]=? *\d+ *[^|]&* *")
###isopattern2 = re.compile(r"idMVA\w+_2 *!?[<=>]=? *\d+ *[^|]&* *")
###def invertiso(cuts,**kwargs):
###  """Helpfunction to find, invert and replace isolation selections."""
###  
###  verbosity   = LOG.getverbosity(kwargs)
###  channel     = kwargs.get('channel', 'emu' )
###  iso_relaxed = kwargs.get('to',      ''    )
###  remove1     = kwargs.get('remove1', True  )
###  cuts0       = cuts
###  
###  # MATCH isolations
###  match_iso_1 = isopattern1.findall(cuts)
###  match_iso_2 = isopattern2.findall(cuts)
###  LOG.verbose('invertIsolationNanoAOD:\n>>>   match_iso_1 = %r\n>>>   match_iso_2 = %r'%(match_iso_1,match_iso_2),verbosity,level=2)
###  
###  # REPLACE
###  if match_iso_1 and match_iso_2:
###    if len(match_iso_1)>1: LOG.warn("invertIsolationNanoAOD: More than one iso_1 match! cuts=%s"%cuts)
###    if len(match_iso_2)>1: LOG.warn("invertIsolationNanoAOD: More than one iso_2 match! cuts=%s"%cuts)
###    if remove1:
###      cuts = cuts.replace(match_iso_1[0],'')
###    cuts = cuts.replace(match_iso_2[0],'')
###    if iso_relaxed:
###      cuts = combineCuts(cuts,iso_relaxed)
###  elif cuts and match_iso_1 or match_iso_2:
###      LOG.warn('invertIsolationNanoAOD: %d iso_1 and %d iso_2 matches! cuts=%r'%(len(match_iso_1),len(match_iso_2),cuts))
###  cuts = cleanBooleans(cuts)
###  
###  LOG.verbose('  %r\n>>>   -> %r\n>>>'%(cuts0,cuts),verbosity,level=2)
###  return cuts
  

###def relaxjetcuts(cuts,**kwargs):
###  """Helpfunction to find, relax and replace jet selections:
###       1) remove b tag requirements
###       2) relax central jet requirements.
###  """
###  ncjets_relaxed  = "ncjets>1" if "ncjets==2" in cuts.replace(' ','') else "ncjets>0"
###  verbosity       = LOG.getverbosity(kwargs)
###  channel         = kwargs.get('channel', 'mutau'        )
###  btags_relaxed   = kwargs.get('btags',   ""             )
###  cjets_relaxed   = kwargs.get('ncjets',  ncjets_relaxed )
###  cuts0           = cuts
###  
###  # MATCH PATTERNS
###  btags  = re.findall(r"&* *nc?btag(?:20)? *[<=>]=? *\d+ *",cuts)
###  cjets  = re.findall(r"&* *ncjets(?:20)? *[<=>]=? *\d+ *",cuts)
###  cjets += re.findall(r"&* *nc?btag(?:20)? *[<=>]=? *ncjets(?:20)? *",cuts)
###  LOG.verbose('relaxJetSelection:\n>>>   btags = %s\n>>>   cjets = %r' % (btags,cjets),verbosity,level=2)
###  if len(btags)>1: LOG.warn('relaxJetSelection: More than one btags match! Only using first instance in cuts %r'%cuts)
###  if len(cjets)>1: LOG.warn('relaxJetSelection: More than one cjets match! Only using first instance in cuts %r'%cuts)
###  
###  # REPLACE
###  #if len(btags):
###  #    cuts = cuts.replace(btags[0],'')
###  #    if btags_relaxed: cuts = "%s && %s"%(cuts,btags_relaxed)
###  #if len(cjets):
###  #    cuts = cuts.replace(cjets[0],'')
###  #    cuts = "%s && %s"%(cuts,cjets_relaxed)
###  if len(btags) and len(cjets):
###      cuts = cuts.replace(btags[0],'')
###      cuts = cuts.replace(cjets[0],'')
###      if btags_relaxed: cuts = "%s && %s && %s" % (cuts,btags_relaxed,cjets_relaxed)
###      else:             cuts = "%s && %s"       % (cuts,              cjets_relaxed)
###  #elif len(btags) or len(cjets):
###  #    LOG.warn("relaxJetSelection: %d btags and %d cjets matches! cuts=%s"%(len(btags),len(cjets),cuts))
###  cuts = cuts.lstrip(' ').lstrip('&').lstrip(' ')
###  
###  LOG.verbose('  %r\n>>>   -> %r\n>>>'%(cuts0,cuts),verbosity,level=2)
###  return cuts
  

####tgmpatternTT = re.compile(r"genmatch_1 *== *5 *&& *genmatch_2 *== *5")
###tgmpatternJJ = re.compile(r"\( *genmatch_1 *!= *5 *\|\| *genmatch_2 *!= *5 *\)")
###tgmpatternLL = re.compile(r"\(genmatch_2 *> *0 *&& *genmatch_2 *(<|!=) *5\)")
###tidpattern   = re.compile(r"(\* *\( *genmatch_[12] *==[^)]*\?[^)]*\))")
###tgmpattern2  = re.compile(r"(genmatch_2 *(!?[<=>]=? *\d))(?! *\?)")
###tgmpattern1  = re.compile(r"(genmatch_1 *(!?[<=>]=? *\d))(?! *\?)")
###def vetojtf(cuts,**kwargs):
###  """Helpfunction to ensure the jet to tau fakes (genmatch==0) are excluded in selection string.
###     Assume string contains gen_match_2 compared to any digits from 1 to 6.
###   """
###  verbosity  = LOG.getverbosity(kwargs)
###  removeTID  = kwargs.get('noTID',   False    )
###  channel    = kwargs.get('channel', "tautau" ) # TODO: generalize
###  cuts0      = cuts
###  
###  # TAU ID SF
###  if removeTID:
###    cuts     = tidpattern.sub("",cuts)
###  
###  # GENMATCH
###  if "tautau" in channel:
###    match1 = tgmpattern1.findall(cuts)
###    match2 = tgmpattern2.findall(cuts)
###    if len(match1)==0 and len(match2)==0:
###      subcuts0 = stripWeights(cuts)
###      subcuts1 = combineCuts(subcuts0,"genmatch_1>0 && genmatch_2>0")
###      cuts     = cuts.replace(subcuts0,subcuts1)
###      return cuts
###    matchJJ    = tgmpatternJJ.findall(cuts)
###    if matchJJ:
###       cuts = cuts.replace(matchJJ[0],"genmatch_1>0 && genmatch_2>0 && %s"%(matchJJ[0]))
###       return cuts
###    if len(match1)>0:
###      match, genmatch = match1[0]
###      if "!=" in genmatch:
###        if '5' in genmatch:
###          cuts = cuts.replace(match,"(genmatch_1!=5 && genmatch_1>0)")
###        elif '0' not in genmatch:
###          cuts = cuts.replace(match,"genmatch_1>0")
###    if len(match2)>0:
###      match, genmatch = match2[0]
###      if "!=" in genmatch:
###        if '5' in genmatch:
###          cuts = cuts.replace(match,"(genmatch_2!=5 && genmatch_2>0)")
###        elif '0' not in genmatch:
###          cuts = cuts.replace(match,"genmatch_2>0")
###  else:
###    match      = tgmpattern2.findall(cuts)
###    if len(match)==0:
###      subcuts0 = stripWeights(cuts)
###      subcuts1 = combineCuts(subcuts0,"genmatch_2>0")
###      cuts     = cuts.replace(subcuts0,subcuts1)
###      return cuts
###    elif len(match)>1:
###      for match, genmatch in match:
###        if '>0' in genmatch.replace(' ','') or '!=0' in genmatch.replace(' ',''):
###          LOG.warn('vetojtf: more than one "genmatch" match (%d) in %r, ignoring...'%(len(match),cuts))
###          return cuts
###      LOG.warn('vetojtf: more than one "genmatch" match (%d) in %r, only looking at first match...'%(len(match),cuts))
###    match, genmatch = match[0]
###    genmatch = genmatch.replace(' ','')
###    subcuts0 = stripWeights(cuts)
###    subcuts1 = subcuts0
###    
###    if '!=' in genmatch:
###      if '5' in genmatch: # "genmatch_2!=5"
###        subcuts1 = subcuts0.replace(match,"genmatch_2!=5 && genmatch_2>0")
###      elif not '0' in genmatch: # "genmatch_2!=*"
###        subcuts1 = combineCuts(subcuts0,"genmatch_2>0")
###    elif "=0" in genmatch: # "genmatch_2*=6"
###        LOG.warn('vetojtf: selection %r with %r set to "0"!'%(cuts,genmatch)) 
###        subcuts1 = "0"
###    elif '<' in genmatch: # "genmatch_2>*"
###        subcuts1 = combineCuts(subcuts0,"genmatch_2>0")
###    cuts = cuts.replace(subcuts0,subcuts1)
###  
###  #LOG.verbose('  %r\n>>>   -> %r\n>>>'%(cuts0,cuts),verbosity,level=2)
###  return cuts
  

def filtervars(vars,filters,**kwargs):
  """Filter list of variables. Allow glob patterns."""
  verbosity = LOG.getverbosity(kwargs)
  newvars   = [ ]
  if not filters:
    return vars[:]
  for var in vars:
    strs = [var] if isinstance(var,str) else set([var.name,var.filename])
    if any(match(f,strs) for f in filters):
      newvars.append(var)
      LOG.verb("filtervars: Matched %r to %r, including..."%(var,filters),verbosity,2)
    else:
      LOG.verb("filtervars: %r NOT matched to %r, ignoring..."%(var,filters),verbosity,2)
  return newvars

#from TauFW.Plotter.plot.Selection import Selection
