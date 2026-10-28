#! /usr/bin/env python
# Author: Izaak Neutelings (August 2020)
# Description: Simple plotting script for pico analysis tuples
# Renamed from Plotter/plot.py (CL §21, Yagizhan Dinckurt, October 2026): it fills the histograms and, by default,
# also draws them, exactly as plot.py did. With --hists it writes them to a file for Plotter/draw.py; with
# --hists --no-draw it only writes the file (the controlhists stage of the Framework runs it so).
# Instructions:
#   ./fillhists.py -y 2018 -c mutau
#   ./fillhists.py -y 2018 -c ../Configs/Histogrammer/setups/setup_mutau.yml
#   ./fillhists.py -y 2018 -c mutau -S baseline -V m_vis
#>>>>IMPORTANT!!
#>>>>Run with --serial option if using py3:
#   ./fillhists.py -y 2018 -c mutau --serial

import os
from config.samples_v15 import *
from TauFW.Histogrammer.spec.string import filtervars
from TauFW.Utilities.Drawing import LOG as PLOG
from TauFW.Histogrammer.controlhists import stack_entry, write_control_hists, normalisation_lumi # --hists (CL §21, S3)
import TauFW.Histogrammer.sample.utils as GLOB # the cme of the normalisation (setera), for --hists (CL §26)
from TauFW.Histogrammer.sample.tupledir import script_default_tuples # LEGACY: picodir without --tuples (CL §37)
import yaml
from TauFW.Utilities.FIO import FileIO
SETUPS = os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","Configs","Histogrammer","setups") # channel setups (CL §20)


def plot(sampleset,setup,parallel=True,tag="",extratext="",outdir="plots",era="",
         varfilter=None,selfilter=None,fraction=False,pdf=False,histfile=None,draw=True):
  """Test plotting of SampleSet class for data/MC comparison.
  With histfile (a path; $ERA, $CHANNEL replaced), the histograms of every stack are also written to that file as
  they were filled, before they are drawn (TauFW.Histogrammer.controlhists; Plotter/draw.py draws them).
  With draw=False (--no-draw, CL §21 S4) nothing is drawn and no plot directory is made: only the file is written.
  The setup's 'qcd: false' leaves out the data-driven QCD estimate (CL §43); without it, QCD_OSSS as before."""
  LOG.header("plot")
  
  channel  = setup["channel"]
  qcdmethod = 'QCD_OSSS' if setup.get('qcd',True) is not False else None # OS/SS QCD unless the setup says qcd: false
  
  if 'baselineCuts' in setup: # baseline pre-selections
    baseline = setup['baselineCuts']
  else:
    raise IOError("No baseline selection for channel %r defined!"%(channel))
  
  selections = [ # plot these selections
    Sel('baseline',baseline)
  ]
  if 'regions' in setup: # add extra regions on top of baseline
    for region in setup['regions']:
      skwargs = setup['regions'][region].copy() # extra key-word options
      assert 'definition' in skwargs
      selstr = setup['baselineCuts']+" && "+skwargs.pop('definition')
      selections.append(Sel(region,selstr,**skwargs))
  selections = filtervars(selections,selfilter) # filter variable list with -S/--sel flag
  
  # VARIABLES
  variables = [
    Var('pt_1',  "Muon pt",    40,  0, 120, ctitle={'etau':"Electron pt",'tautau':"Leading tau_h pt",'mumu':"Leading muon pt",'emu':"Electron pt"},cbins={"nbtag\w*>":(40,0,200)}),
    Var('pt_2',  "tau_h pt",   40,  0, 120, ctitle={'tautau':"Subleading tau_h pt",'mumu':"Subleading muon pt",'emu':"Muon pt"},cbins={"nbtag\w*>":(40,0,200)}),
    Var('eta_1', "Muon eta",   30, -3,   3, ctitle={'etau':"Electron eta",'tautau':"Leading tau_h eta",'mumu':"Leading muon eta",'emu':"Electron eta"},ymargin=1.7,pos='T',ncols=2),
    Var('eta_2', "tau_h eta",  30, -3,   3, ctitle={'etau':"Electron eta",'tautau':"Subleading tau_h eta",'mumu':"Subleading muon eta",'emu':"Muon eta"},ymargin=1.7,pos='T',ncols=2),
    Var('mt_1',  "mt(mu,MET)", 40,  0, 200, ctitle={'etau':"mt(mu,MET)",'tautau':"mt(tau,MET)",'emu':"mt(e,MET)"},cbins={"nbtag\w*>":(50,0,250)}),
    Var("jpt_1",  29,   10,  300, veto=[r"njets\w*==0"]),
    # BUGS L01: idDeepTau2018v2p5VSVjet_2 and idDeepTau2018v2p5VSVSe_2 (no such branches) were plotted here for every
    # channel; the tau ID variables are in the tau-channel list below
    Var("jpt_2",  29,   10,  300, veto=[r"njets\w*==0"]),
    Var("jeta_1", 53, -5.4,  5.2, ymargin=1.6,pos='T',ncols=2,veto=[r"njets\w*==0"]),
    Var("jeta_2", 53, -5.4,  5.2, ymargin=1.6,pos='T',ncols=2,veto=[r"njets\w*==0"]),
    Var('npv',    40,  0,  80),
    Var('njets',   8,  0,   8),
    Var('nbtag', "Number of b jets (Medium, pt > 30 GeV)", 8, 0, 8),
    Var('met',    50,  0, 150,cbins={"nbtag\w*>":(50,0,250)}),
    #Var('genmet', 50,  0, 150, fname="$VAR_log", logyrange=4, data=False, logy=True, ncols=2, pos='TT'),
    Var('pt_ll',   "p_{T}(mutau_h)", 25, 0, 200, ctitle={'etau':"p_{T}(etau_h)",'tautau':"p_{T}(tau_htau_h)",'emu':"p_{T}(emu)"}),
    Var('dR_ll',   "DR(mutau_h)",    30, 0, 6.0, ctitle={'etau':"DR(etau_h)",'tautau':"DR(tau_htau_h)",'emu':"DR(emu)"}),
    Var('deta_ll', "deta(mutau_h)",  20, 0, 6.0, ctitle={'etau':"deta(etau_h)",'tautau':"deta(tautau)",'emu':"deta(emu)"},logy=True,pos='TRR',cbins={"abs(deta_ll)<":(10,0,3)}), #, ymargin=8, logyrange=2.6
    Var('dzeta',  56, -180, 100, pos='L;y=0.87',units='GeV',cbins={"nbtag\w*>":(35,-220,130)}),
  ]
  if 'tau' in channel: # mutau, etau, tautau
    # BUGS L11: found next to this script, not in the working directory (which may be any output directory)
    loadmacro(os.path.join(os.path.dirname(os.path.abspath(__file__)),"python/macros/mapDecayModes.C")) # for mapRecoDM
    dmlabels  = ["h^{#pm}","h^{#pm}h^{0}","h^{#pm}h^{#mp}h^{#pm}","h^{#pm}h^{#mp}h^{#pm}h^{0}","Other"]
    variables += [
      Var('m_vis',          40,  0, 200, fname="mvis",ctitle={'mumu':"m_mumu",'emu':"m_emu"},cbins={"pt_\d>":(50,0,250),"nbtag\w*>":(60,0,300)},cpos={"pt_\d>[1678]0":'LL;y=0.88'}),
      Var('m_vis',          20,  50, 150, fname="mvis_coarse",ctitle={'mumu':"m_mumu",'emu':"m_emu"},cbins={"pt_\d>":(25,0,250),"nbtag\w*>":(30,0,300)},cpos={"pt_\d>[1678]0":'LL;y=0.88'}),
      Var("m_2",            30,  0,   3, title="m_tau",veto=["njet","nbtag","dm_2==0"]),
      Var("dm_2",           14,  0,  14, fname="dm_2",title="Reconstructed tau_h decay mode",veto="dm_2==",position="TMC",ymargin=1.2),
      Var("mapRecoDM(dm_2)", 5,  0,   5, fname="dm_2_label",title="Reconstructed tau_h decay mode",veto="dm_2==",position="TT",labels=dmlabels,ymargin=1.2),
      #Var("pzetavis", 50,    0, 200 ),
      Var('idDeepTau2018v2p5VSjet_2', "DeepTau2018v2p5VSjet", 8, 0, 7, fname="$VAR_zoom",ncols=2,pos='L;y=0.85'),
      Var('idDeepTau2018v2p5VSe_2',   "DeepTau2018v2p5VSe",  8, 0, 7, fname="$VAR_zoom",ncols=2,logy=True,logyrange=4,pos='L;y=0.85'), # BUGS L01: was VSVSe
      Var('rawDeepTau2018v2p5VSmu_2',  "rawDeepTau2018v2p5VSmu",  40, -1, 1, fname="$VAR_zoom",ncols=2,logy=True,logyrange=5,pos='L;y=0.85'),
      Var('rawPNetVSjet_2', "rawPNetVSjet", 40, -1, 1, fname="$VAR_zoom",ncols=2,pos='L;y=0.85'),
      Var('rawPNetVSe_2',   "rawPNetVSe",   40, -1, 1, fname="$VAR_zoom",ncols=2,logy=True,logyrange=4,pos='L;y=0.85'),
      Var('rawPNetVSmu_2',  "rawPNetVSmu",  40, -1, 1, fname="$VAR_zoom",ncols=2,logy=True,logyrange=5,pos='L;y=0.85'),
      Var('rawUParTVSjet_2', "rawUParTVSjet", 40, -1, 1, fname="$VAR_zoom",ncols=2,pos='L;y=0.85'),
      Var('rawUParTVSe_2',   "rawUParTVSe",   40, -1, 1, fname="$VAR_zoom",ncols=2,logy=True,logyrange=4,pos='L;y=0.85'),
      Var('rawUParTVSmu_2',  "rawUParTVSmu",  40, -1, 1, fname="$VAR_zoom",ncols=2,logy=True,logyrange=5,pos='L;y=0.85'),
    ]
  elif 'mumu' in channel:
    variables += [
      Var('m_ll', "m_mumu", 40,  0,  200, fname="$VAR", cbins={"m_vis>200":(40,200,1000)}), # alias: m_ll alias of m_vis
      Var('m_ll', "m_mumu", 40,  0,  200, fname="$VAR_log", logy=True, ymin=1e2, cbins={"m_vis>200":(40,200,1000)} ),
      Var('m_ll', "m_mumu", 40, 70,  110, fname="$VAR_Zmass", veto=["m_vis>200"] ),
      Var('m_ll', "m_mumu",  1, 70,  110, fname="$VAR_1bin", veto=["m_vis>200"] ),
      Var('m_vis',          40,  0, 200, fname="mvis",ctitle={'mumu':"m_mumu",'emu':"m_emu"},cbins={"pt_\d>":(50,0,250),"nbtag\w*>":(60,0,300)},cpos={"pt_\d>[1678]0":'LL;y=0.88'}),
      Var('m_vis',          1,  0, 200, fname="mvis_1bin",ctitle={'mumu':"m_mumu",'emu':"m_emu"},cbins={"pt_\d>":(50,0,250),"nbtag\w*>":(60,0,300)},cpos={"pt_\d>[1678]0":'LL;y=0.88'}),

    ]
  variables  = filtervars(variables,varfilter)  # filter variable list with -V/--var flag
  
  # PLOT
  if draw:
    outdir = FileIO().make_directory(repkey(outdir,CHANNEL=channel,ERA=era))
  exts   = ['png','pdf'] if pdf else ['png'] # extensions
  entries = [ ] # --hists: the histograms of every stack, as filled
  for selection in selections:
    print(">>> Selection %r: %r"%(selection.title,selection.selection))
    stacks = sampleset.getstack(variables,selection,method=qcdmethod,parallel=parallel)
    fname  = "%s/$VAR_%s-%s-%s$TAG"%(outdir,channel.replace('mu','m').replace('tau','t'),selection.filename,era)
    text   = "%s: %s"%(channel.replace('mu',"#mu").replace('tau',"#tau_{h}"),selection.title)
    if extratext:
      text += ("" if '\n' in extratext[:3] else ", ") + extratext
    for stack, variable in stacks.items():
      if histfile: # copies of the histograms BEFORE draw() changes them; variable = (Variable, Selection)
        entries.append(stack_entry(stack,*variable))
      if not draw: # --no-draw: the file is the output
        continue
      #position = "" #variable.position or 'topright'
      stack.draw(fraction=fraction)
      stack.drawlegend() #position)
      stack.drawtext(text)
      stack.saveas(fname,ext=exts,tag=tag)
      stack.close(keep=True)
  if histfile:
    histfile = write_control_hists(repkey(histfile,CHANNEL=channel,ERA=era),entries,channel=channel,era=era,
                                   lumi=normalisation_lumi(sampleset.mcsamples),cme=GLOB.cme,tag=tag)
    print(">>> Wrote the histograms of %d stacks to %s (draw them with Plotter/draw.py)"%(len(entries),histfile))


def main(args):
  configs   = args.configs
  eras      = args.eras
  parallel  = args.parallel
  varfilter = args.varfilter
  selfilter = args.selfilter
  notauidsf = args.notauidsf
  extratext = args.text
  fraction  = args.fraction
  pdf       = args.pdf
  outdir    = "plots/$ERA"
  fname     = "$PICODIR/$SAMPLE_$CHANNEL$TAG.root"
  tuples    = args.tuples # None: picodir of the PicoProducer configuration (script_default_tuples)
  samples   = args.samples # sample model files, one per era; None: the tables of config/samples_v15.py
  
  # LOOP over configs / channels
  for config in configs:
    if not config.endswith(".yml"): # config = channel name
      config = os.path.join(SETUPS,"setup_%s.yml"%(config)) # assume this file name pattern
    print(">>> Using configuration file: %s"%config)
    with open(config, 'r') as file:
      setup = yaml.safe_load(file)
    tag = setup.get('tag',"")+args.tag
    histfile = "hists/$ERA/$CHANNEL%s.root"%(tag) if args.hists else None # --hists: next to plots/$ERA

    for era in eras:
      setera(era) # set era for plot style and lumi-xsec normalization
      addsfs = [ ] #"getTauIDSF(dm_2,genmatch_2)"]
      rmsfs  = [ ] if (setup['channel']=='mumu' or not notauidsf) else ['idweight_2','ltfweight_2'] # remove tau ID SFs
      split  = ['DY'] if 'tau' in setup['channel'] else [ ] # split these backgrounds into tau components
      sampleset = getsampleset(setup['channel'],era,fname=fname,rmsf=rmsfs,addsf=addsfs,split=split,
                               tuples=tuples or script_default_tuples(),samples=samples)
      plot(sampleset,setup,parallel=parallel,tag=tag,extratext=extratext,outdir=outdir,era=era,
           varfilter=varfilter,selfilter=selfilter,fraction=fraction,pdf=pdf,histfile=histfile,draw=args.draw)
      #sampleset.close()
  

if __name__ == "__main__":
  from argparse import ArgumentParser, RawTextHelpFormatter
  eras = ['2016','2017','2018','UL2016_preVFP','UL2016_postVFP','UL2017','UL2018','2022_preEE','2022_postEE','2023C','2023D','2024', '2025', '2026', '2526']
  description = """Simple plotting script for pico analysis tuples"""
  parser = ArgumentParser(prog="fillhists",description=description,epilog="Good luck!")
  parser.add_argument('-y', '--era',     dest='eras', nargs='*', choices=eras, default=['2017'],
                                         help="set era" )
  parser.add_argument('-c', '--config', '--channel',
                                         dest='configs', type=str, nargs='+', default=['mutau_inclusive'], action='store',
                                         help="config file(s) containing channel setup for samples and selections, default=%(default)r" )
  parser.add_argument('-V', '--var',     dest='varfilter', nargs='+',
                                         help="only plot the variables passing this filter (glob patterns allowed)" )
  parser.add_argument('-S', '--sel',     dest='selfilter', nargs='+',
                                         help="only plot the selection passing this filter (glob patterns allowed)" )
  parser.add_argument('-s', '--serial',  dest='parallel', action='store_false',
                                         help="run Tree::MultiDraw serial instead of in parallel" )
  parser.add_argument('-F', '--fraction',dest='fraction', action='store_true',
                                         help="include fraction stack in ratio plot" )
  parser.add_argument('-p', '--pdf',     dest='pdf', action='store_true',
                                         help="create pdf version of each plot" )
  parser.add_argument('-r', '--nosf',    dest='notauidsf', action='store_true',
                                         help="remove DeepTau ID SF" )
  parser.add_argument('-t', '--tag',     default="", help="extra tag for output" )
  parser.add_argument('-T', '--text',    default="", help="extra text on plot" )
  parser.add_argument('--tuples',        default=None, metavar='PATTERN',
                                         help="directory pattern of the input tuples, e.g. /eos/.../$ERA/$GROUP "
                                              "(files <sample>_<channel>.root), instead of $PICODIR of the "
                                              "PicoProducer configuration" )
  parser.add_argument('--samples',       default=None, nargs='+', metavar='FILE',
                                         help="sample model files, one per era (e.g. Configs/Histogrammer/samples/v15_2025.yml "
                                              "or a copy), instead of the tables of config/samples_v15.py" )
  parser.add_argument('--hists',         action='store_true',
                                         help="also write the filled histograms of every plot to "
                                              "hists/<era>/<channel><tag>.root, for Plotter/draw.py (CL §21)" )
  parser.add_argument('--no-draw',       dest='draw', action='store_false',
                                         help="with --hists: only write the histogram file, draw nothing "
                                              "(Plotter/draw.py draws it; CL §21)" )
  parser.add_argument('-v', '--verbose', dest='verbosity', type=int, nargs='?', const=1, default=0, action='store',
                                         help="set verbosity" )
  args = parser.parse_args()
  if not args.draw and not args.hists: # nothing would be written
    parser.error("--no-draw needs --hists (without the file nothing would be written)")
  if not args.draw and (args.fraction or args.pdf or args.text):
    print(">>> Warning: --no-draw: the drawing options -F/-p/-T are ignored (give them to Plotter/draw.py)")
  LOG.verbosity = args.verbosity
  PLOG.verbosity = args.verbosity
  main(args)
  print("\n>>> Done.")
  
