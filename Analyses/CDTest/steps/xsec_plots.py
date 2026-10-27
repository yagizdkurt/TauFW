# Plots of the Z cross-section fit (Fit 2) for the CDTest python step steps/xsec_fit.py: a copy of long-ex
# Plotter/plot_xsec_results.py (CMSDAS26 Tau long exercise) without its command line (main), so that the plots are
# the exercise's; changed: plot_summary returns its values. Long-ex style (two-space indentation) kept on purpose.
#   plot_mvis(indir, outdir, channel, stage, lumi, era)   pre-/post-fit m_vis (postfit_shapes_<channel>.root)
#   plot_pulls(indir, outdir, channel, lumi, era)          nuisance pulls (fitDiagnostics.xsec_<channel>.root)
#   plot_summary(indir, outdir, lumi, era)                 r(mutau), r(mumu), ratio (NLL scans); returns the values
import os
from array import array
import ROOT as R
R.gROOT.SetBatch(True)
R.gStyle.SetOptStat(0)
R.gStyle.SetOptTitle(0)
R.gErrorIgnoreLevel = R.kWarning

# stacking order (bottom -> top), colors as in the control plots (Plotter/python/sample/SampleStyle.py)
STACK_ORDER = ['QCD', 'VV',  'Top',  'WJ', 'ZJ', 'ZL', 'ZTT']
COLORS = {'ZTT': R.kOrange-4, 'ZL': R.kAzure+5, 'ZJ': R.kGreen-6, 'Top': R.kBlue-8, 'VV': 45,
          'WJ': 50, 'QCD': R.kMagenta-10}
TITLES = {'ZTT': "Z #rightarrow #tau_{#mu}#tau_{h}", 'ZL': "Z #rightarrow ll, l #rightarrow #tau_{h}",
          'ZJ': "Z + jets, j #rightarrow #tau_{h}", 'Top': "t#bar{t} and single t", 'VV': "Diboson",
          'WJ': "W + jets", 'QCD': "QCD multijet"}
CHANNEL_TITLES = {'mutau': "#mu#tau_{h}", 'mumu': "#mu#mu"}


def cmslabel(lumi, era, left=0.16, right=0.96, top=0.945, size=0.045):
  """Draw 'CMS Internal' and the luminosity label above the current pad."""
  tex = R.TLatex()
  tex.SetNDC(True)
  tex.SetTextFont(62); tex.SetTextSize(size); tex.SetTextAlign(11)
  tex.DrawLatex(left, top, "CMS")
  tex.SetTextFont(52); tex.SetTextSize(0.8*size)
  tex.DrawLatex(left + 2.4*size, top, "Internal")
  tex.SetTextFont(42); tex.SetTextAlign(31)
  tex.DrawLatex(right, top, "%s, %s fb^{-1} (13.6 TeV)" % (era, lumi))
  return tex


def save(canvas, outdir, name):
  for ext in ('pdf', 'png'):
    canvas.SaveAs(os.path.join(outdir, "%s.%s" % (name, ext)))
  print(">>> wrote %s.pdf/.png" % os.path.join(outdir, name))


def plot_mvis(indir, outdir, channel, stage, lumi, era):
  """Stack of the m_vis templates before ('prefit') or after ('postfit') the fit, with the total
  uncertainty band and the data/prediction ratio."""
  fname = os.path.join(indir, "postfit_shapes_%s.root" % channel)
  fin = R.TFile.Open(fname) if os.path.exists(fname) else None
  if not fin or fin.IsZombie():
    print(">>> skip m_vis %s (%s): %s not found" % (stage, channel, fname))
    return
  d = fin.Get("%s_%s" % (channel, stage))
  data, total = d.Get("data_obs"), d.Get("TotalProcs")
  procs = [p for p in STACK_ORDER if d.Get(p)]
  width = data.GetXaxis().GetBinWidth(1)
  isscore = data.GetXaxis().GetXmax() <= 1.0  # a BDT score (docs/CMSDAS26/bdt.md) instead of m_vis
  xtitle = "BDT score" if isscore else "m_{vis} [GeV]"
  ytitle = "Events / %g" % width if isscore else "Events / %g GeV" % width

  canvas = R.TCanvas("c_mvis_%s_%s" % (channel, stage), "", 800, 800)
  top = R.TPad("top", "", 0, 0.30, 1, 1); top.SetMargin(0.16, 0.04, 0.02, 0.09); top.Draw()
  bot = R.TPad("bot", "", 0, 0, 1, 0.30); bot.SetMargin(0.16, 0.04, 0.36, 0.03); bot.Draw()

  top.cd()
  stack = R.THStack("stack", "")
  hists = []
  for p in procs:
    h = d.Get(p)
    h.SetFillColor(COLORS.get(p, R.kGray)); h.SetLineColor(R.kBlack); h.SetLineWidth(1)
    stack.Add(h)
    hists.append((p, h))
  stack.Draw("HIST")
  stack.SetMaximum(1.35*max(data.GetMaximum(), total.GetMaximum()))
  stack.GetXaxis().SetLabelSize(0)
  stack.GetYaxis().SetTitle(ytitle)
  stack.GetYaxis().SetNoExponent(True)
  stack.GetYaxis().SetTitleSize(0.055); stack.GetYaxis().SetLabelSize(0.042); stack.GetYaxis().SetTitleOffset(1.45)
  band = total.Clone("band")
  band.SetFillColor(R.kBlack); band.SetFillStyle(3354); band.SetMarkerSize(0); band.SetLineWidth(0)
  band.Draw("E2 SAME")
  data.SetMarkerStyle(20); data.SetMarkerSize(1.0); data.SetLineColor(R.kBlack)
  data.Draw("E0 X0 SAME")

  legend = R.TLegend(0.62, 0.42, 0.93, 0.88)
  legend.SetBorderSize(0); legend.SetFillStyle(0); legend.SetTextSize(0.042)
  legend.AddEntry(data, "Observed", "pe")
  for p, h in reversed(hists):
    legend.AddEntry(h, TITLES.get(p, p), "f")
  legend.AddEntry(band, "%s unc." % ("Pre-fit" if stage == 'prefit' else "Post-fit"), "f")
  legend.Draw()
  cmslabel(lumi, era, left=0.16)
  tex = R.TLatex(); tex.SetNDC(True); tex.SetTextFont(42); tex.SetTextSize(0.048)
  tex.DrawLatex(0.21, 0.83, "%s, %s" % (CHANNEL_TITLES.get(channel, channel), "pre-fit" if stage == 'prefit' else "post-fit"))

  bot.cd()
  ratio = data.Clone("ratio")
  rband = total.Clone("rband")
  for i in range(1, total.GetNbinsX() + 1):
    t, te = total.GetBinContent(i), total.GetBinError(i)
    ratio.SetBinContent(i, data.GetBinContent(i)/t if t > 0 else 0)
    ratio.SetBinError(i, data.GetBinError(i)/t if t > 0 else 0)
    rband.SetBinContent(i, 1)
    rband.SetBinError(i, te/t if t > 0 else 0)
  rband.SetFillColor(R.kBlack); rband.SetFillStyle(3354); rband.SetMarkerSize(0); rband.SetLineWidth(0)
  rband.GetYaxis().SetRangeUser(0.71, 1.29)
  rband.GetYaxis().SetTitle("Obs. / Pred."); rband.GetYaxis().CenterTitle(True)
  rband.GetYaxis().SetNdivisions(505)
  rband.GetYaxis().SetTitleSize(0.12); rband.GetYaxis().SetLabelSize(0.10); rband.GetYaxis().SetTitleOffset(0.65)
  rband.GetXaxis().SetTitle(xtitle)
  rband.GetXaxis().SetTitleSize(0.14); rband.GetXaxis().SetLabelSize(0.115); rband.GetXaxis().SetTitleOffset(1.1)
  rband.Draw("E2")
  line = R.TLine(rband.GetXaxis().GetXmin(), 1, rband.GetXaxis().GetXmax(), 1)
  line.SetLineStyle(2); line.Draw()
  ratio.Draw("E0 X0 SAME")
  bot.SetGridy(True)
  save(canvas, outdir, "mvis_%s_%s" % (stage, channel))
  fin.Close()


def load_fit(indir, channel):
  """Return (file, RooFitResult fit_s) from the FitDiagnostics output of a channel."""
  for tag in (".xsec_", ".shapes_"):
    fname = os.path.join(indir, "fitDiagnostics%s%s.root" % (tag, channel))
    if os.path.exists(fname):
      fin = R.TFile.Open(fname)
      fit = fin.Get("fit_s")
      if fit:
        return fin, fit
  return None, None


def plot_pulls(indir, outdir, channel, lumi, era):
  """Post-fit value and uncertainty of each nuisance parameter, in units of its pre-fit uncertainty
  (pre-fit = 0 +- 1). The per-bin MC-stat parameters (prop_*) are left out."""
  fin, fit = load_fit(indir, channel)
  if not fit:
    print(">>> skip pulls (%s): no fitDiagnostics file with fit_s in %s" % (channel, indir))
    return
  pars = fit.floatParsFinal()
  rows = []
  for i in range(pars.getSize()):
    p = pars.at(i)
    if p.GetName() == 'r' or p.GetName().startswith('prop_'):
      continue
    rows.append((p.GetName(), p.getVal(), p.getError()))
  rows.sort(key=lambda x: -abs(x[1]))  # largest pull on top
  n = len(rows)

  canvas = R.TCanvas("c_pulls_%s" % channel, "", 800, 220 + 55*n)
  canvas.SetMargin(0.22, 0.24, 110./(220 + 55*n), 70./(220 + 55*n))
  frame = R.TH2F("frame_pulls_%s" % channel, "", 10, -3, 3, n, 0, n)
  for j, (name, val, err) in enumerate(rows):
    frame.GetYaxis().SetBinLabel(n - j, name)
  frame.GetXaxis().SetTitle("(#hat{#theta} - #theta_{0}) / #sigma_{pre-fit}")
  frame.GetXaxis().SetTitleSize(0.045); frame.GetXaxis().SetLabelSize(0.04)
  frame.GetYaxis().SetLabelSize(0.05)
  frame.Draw()
  boxes = []
  for lim, col in ((2, R.kOrange), (1, R.kGreen+1)):
    box = R.TBox(-lim, 0, lim, n); box.SetFillColor(col); box.SetLineWidth(0); box.Draw()
    boxes.append(box)
  zero = R.TLine(0, 0, 0, n); zero.SetLineStyle(2); zero.Draw()
  graph = R.TGraphAsymmErrors(n)
  tex = R.TLatex(); tex.SetTextFont(42); tex.SetTextSize(0.04); tex.SetTextAlign(12)
  for j, (name, val, err) in enumerate(rows):
    y = n - j - 0.5
    graph.SetPoint(j, val, y)
    graph.SetPointError(j, err, err, 0, 0)
    tex.DrawLatex(3.15, y, "%+.2f #pm %.2f" % (val, err))
  graph.SetMarkerStyle(20); graph.SetMarkerSize(1.2); graph.SetLineWidth(2)
  graph.Draw("P SAME")
  R.gPad.RedrawAxis()
  cmslabel(lumi, era, left=0.22, right=0.76, top=1 - 55./(220 + 55*n), size=0.045)
  tex2 = R.TLatex(); tex2.SetNDC(True); tex2.SetTextFont(42); tex2.SetTextSize(0.04); tex2.SetTextAlign(13)
  tex2.DrawLatex(0.78, 1 - 20./(220 + 55*n), "%s fit" % CHANNEL_TITLES.get(channel, channel))
  save(canvas, outdir, "pulls_%s" % channel)
  fin.Close()


def scan_interval(fname):
  """Best-fit r and its 68% interval (-2 Delta ln L = 1) from a MultiDimFit grid scan.
  Returns (best, err_down, err_up). The crossing is interpolated linearly in sqrt(-2 Delta ln L),
  which is exact for a parabola, so it also works when the grid is coarse compared to the interval
  (as for the very narrow stat-only curves)."""
  fin = R.TFile.Open(fname) if os.path.exists(fname) else None
  if not fin or fin.IsZombie():
    return None
  tree = fin.Get("limit")
  best, points = None, []
  for ev in tree:
    y = 2*ev.deltaNLL
    if y != y:
      continue  # failed grid point
    if ev.quantileExpected == -1:
      best = ev.r
    else:
      points.append((ev.r, y))
  fin.Close()
  if best is None or not points:
    return None
  def crossing(side):
    pts = sorted([p for p in points if (p[0] - best)*side > 0], key=lambda p: abs(p[0] - best))
    prev = (0., 0.)  # (distance from the best fit, sqrt(-2 Delta ln L))
    for x, y in pts:
      d, s = abs(x - best), max(y, 0.)**0.5
      if s >= 1:
        return prev[0] + (d - prev[0])*(1 - prev[1])/(s - prev[1])
      prev = (d, s)
    return None  # scan range does not reach -2 Delta ln L = 1
  return best, crossing(-1), crossing(+1)


def lumi_correlation(indir, channel):
  """Correlation between r and the luminosity nuisance, from the FitDiagnostics result."""
  fin, fit = load_fit(indir, channel)
  if not fit:
    return 0.
  pars = fit.floatParsFinal()
  names = [pars.at(i).GetName() for i in range(pars.getSize())]
  lumis = [n for n in names if n.startswith('lumi')]
  rho = fit.correlation('r', lumis[0]) if lumis else 0.
  fin.Close()
  return rho


def plot_summary(indir, outdir, lumi, era):
  """r(mutau), r(mumu) and the ratio r(mutau)/r(mumu): total uncertainty as bars, stat-only as text.
  In the ratio the luminosity is taken as fully correlated between the channels, so it cancels;
  all other uncertainties are taken as uncorrelated."""
  res = {}
  for ch in ('mutau', 'mumu'):
    tot = scan_interval(os.path.join(indir, "higgsCombine.scan_%s.MultiDimFit.mH120.root" % ch))
    stat = scan_interval(os.path.join(indir, "higgsCombine.scan_%s_statonly.MultiDimFit.mH120.root" % ch))
    if not tot or None in tot:
      print(">>> skip summary: no valid total NLL scan for %s in %s" % (ch, indir))
      return
    statlo, stathi = (stat[1] or 0., stat[2] or 0.) if stat else (0., 0.)
    res[ch] = dict(r=tot[0], lo=tot[1], hi=tot[2], statlo=statlo, stathi=stathi,
                   rho=lumi_correlation(indir, ch))
  mt, mm = res['mutau'], res['mumu']
  ratio = mt['r']/mm['r']
  def nolumi(x, key):  # uncertainty left after removing the part correlated with the luminosity
    return x[key]*max(0., 1 - x['rho']**2)**0.5/x['r']
  res['ratio'] = dict(r=ratio,
    lo=ratio*(nolumi(mt, 'lo')**2 + nolumi(mm, 'hi')**2)**0.5,
    hi=ratio*(nolumi(mt, 'hi')**2 + nolumi(mm, 'lo')**2)**0.5,
    statlo=ratio*((mt['statlo']/mt['r'])**2 + (mm['stathi']/mm['r'])**2)**0.5,
    stathi=ratio*((mt['stathi']/mt['r'])**2 + (mm['statlo']/mm['r'])**2)**0.5)

  rows = [('mutau', "r(Z #rightarrow #tau_{#mu}#tau_{h})"), ('mumu', "r(Z #rightarrow #mu#mu)"),
          ('ratio', "r(#tau_{#mu}#tau_{h}) / r(#mu#mu)")]
  n = len(rows)
  canvas = R.TCanvas("c_summary", "", 900, 520)
  canvas.SetMargin(0.24, 0.30, 0.16, 0.10)
  frame = R.TH2F("frame_summary", "", 10, 0.90, 1.10, n, 0, n)
  for j, (key, title) in enumerate(rows):
    frame.GetYaxis().SetBinLabel(n - j, title)
  frame.GetXaxis().SetTitle("r = #sigma / #sigma_{theory}")
  frame.GetXaxis().SetTitleSize(0.05); frame.GetXaxis().SetLabelSize(0.045); frame.GetXaxis().SetNdivisions(505)
  frame.GetYaxis().SetLabelSize(0.065)
  frame.Draw()
  one = R.TLine(1, 0, 1, n); one.SetLineStyle(2); one.SetLineColor(R.kGray+2); one.Draw()
  sep = R.TLine(0.90, 1, 1.10, 1); sep.SetLineColor(R.kGray+1); sep.Draw()
  gtot = R.TGraphAsymmErrors(n)
  tex = R.TLatex(); tex.SetTextFont(42); tex.SetTextSize(0.045); tex.SetTextAlign(12)
  for j, (key, title) in enumerate(rows):
    x, y = res[key], n - j - 0.5
    gtot.SetPoint(j, x['r'], y)
    gtot.SetPointError(j, x['lo'], x['hi'], 0, 0)
    tex.DrawLatex(1.105, y + 0.14, "%.3f {}^{+%.3f}_{-%.3f} (tot.)" % (x['r'], x['hi'], x['lo']))
    tex.DrawLatex(1.105, y - 0.20, "#pm %.4f (stat.)" % (0.5*(x['statlo'] + x['stathi'])))
    print(">>> %-6s r = %.4f  -%.4f/+%.4f (total)  -%.4f/+%.4f (stat)" % (
          key, x['r'], x['lo'], x['hi'], x['statlo'], x['stathi']))
  gtot.SetLineWidth(2); gtot.SetMarkerStyle(20); gtot.SetMarkerSize(1.3)
  gtot.Draw("P SAME")
  note = R.TLatex(); note.SetNDC(True); note.SetTextFont(42); note.SetTextSize(0.032); note.SetTextAlign(11)
  note.DrawLatex(0.02, 0.025, "Bars: total uncertainty (the stat. part is too small to draw). "
                              "Ratio: luminosity cancels, other uncertainties uncorrelated.")
  R.gPad.RedrawAxis()
  cmslabel(lumi, era, left=0.24, right=0.70, top=0.915, size=0.05)
  save(canvas, outdir, "summary_xsec")
  return res  # CDTest: the values, for the step's table
