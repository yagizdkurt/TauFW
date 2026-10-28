# Author: Izaak Neutelings (April 2020)
"""Status of a sample's jobs: which chunks succeeded, are pending, failed (corrupted output) or are missing.

  check_sample()           the pipeline for one sample:
    1. expected events     from the job config, or from DAS
    2. queue               which of the sample's jobs are still queued or running
    3. classify            a classifier assigns pending jobs and output files to chunks
                           (_SkimClassifier: nanoAOD skims, one or more output files per job;
                            _TreeClassifier: pico trees, one numbered output file per job)
    4. report              the SUCCESS/PEND/FAIL/MISS summary, and the log files of failed chunks

The classifiers decide; they do not touch files, storage or the batch queue. check_sample does those
observations (queue, storage listing, file validation, job lists and logs) and feeds the results in, in the
same order as before, so the output of pico.py is unchanged.

Inputs:  a Sample loaded from its job config (getcfgsamples), the configuration, the batch queue,
         the output files in storage, and a reporter.
Outputs: ChunkStatus (chunk numbers per state, events, the files to resubmit, the chunks to keep);
         the summary lines and log files through the reporter.

Public API:
  check_sample(sample, config, reporter, **options)   -> ChunkStatus
  format_summary(status)                              -> SUCCESS/PEND/FAIL/MISS lines
  ChunkStatus                                         record (near the bottom of this file)
"""

# ===== Imports =====
import os, re, glob, json
from dataclasses import dataclass
from TauFW.common.tools.string import alphanum_key
from TauFW.common.tools.log import Logger, color
from TauFW.PicoProducer.batch.factory import getbatch
from TauFW.PicoProducer.jobs.chunking import evtsplitexp
from TauFW.PicoProducer.jobs.reporting import Reporter
from TauFW.Utilities.FIO import FileIO
from TauFW.PicoProducer.storage.factory import getstorage
from TauFW.PicoProducer.storage.validation import isvalid, itervalid

__all__ = ['check_sample', 'format_summary', 'ChunkStatus']


# ===== Constants =====
LOG = Logger()


# ===== Pipeline =====

def check_sample(sample,config,reporter=None,outdir=None,channel=None,tag=None,checkqueue=-1,checkevts=True,
                 checkexpevts=False,jobs=None,das=True,showlogs=False,ncores=4,verb=0):
  """Check the jobs of a sample's last (re)submission try.
  Options: outdir/channel/tag override the job config; checkqueue: 0 (no check), 1 (reuse jobs), -1 (query);
  checkevts: validate output files and count events; checkexpevts: compare to the expected events per chunk
  (None: analysis jobs only); jobs: queue jobs from an earlier query; das: get the expected events from DAS;
  showlogs: print log files of failed/missing chunks (number, or <0 for all); ncores: parallel validation."""
  reporter   = reporter or Reporter()
  verbosity  = verb
  jobcfg     = sample.jobcfg # job config from last job
  jobids     = jobcfg['jobids']
  filenevts  = sample.filenevts
  if outdir==None:
    outdir   = jobcfg['outdir']
  storage    = getstorage(outdir) # StorageElement instance of output directory; BUGS P22: was ensure=True (created it)
  if channel==None:
    channel  = jobcfg['channel']
  if tag==None:
    tag      = jobcfg['tag']
  if not filenevts:
    checkexpevts = False # BUGS P07: was 'checkexpevts==False', a comparison without effect
  elif checkexpevts==None:
    checkexpevts = 'skim' not in channel.lower() # default for pico analysis jobs

  # 1. NUMBER OF EVENTS
  nexpected = jobcfg['nevents'] # total number of available events
  if das: #and nexpected==0: # get nevents straight from DAS
    nexpected = sample.getnevents(das=True)
  elif verbosity>=2:
    reporter.line(">>> %-12s = %s"%('ndasevents',nexpected))
  if verbosity>=3:
    reporter.line(">>> %-12s = %s"%('chunkdict',jobcfg['chunkdict']))
    reporter.line(">>> %-12s = %s"%('ncores',ncores))

  # 2. CHECK PENDING JOBS
  if checkqueue<0 or jobs:
    if checkqueue!=1 or not jobs:
      batch = getbatch(config,verb=verbosity)
      jobs  = batch.jobs(jobids,verb=verbosity-1) # refresh job list
    elif jobs:
      jobs  = [j for j in jobs if j.jobid in jobids] # get new job list with right job id

  # 3. CLASSIFY pending jobs and output files
  skim       = 'skim' in channel.lower()
  Classifier = _SkimClassifier if skim else _TreeClassifier
  classifier = Classifier(jobcfg,filenevts,checkexpevts,reporter,verbosity)
  classifier.report_settings(checkqueue,jobs)
  if jobs:
    joblines = None # lines of the job list (SGE, SLURM: line i has the arguments of task i+1), read once
    for job in jobs:
      if verbosity>=3:
        reporter.line(">>> Found job %r, status=%r, args=%r"%(job,job.getstatus(),job.args.rstrip()))
      if job.getstatus() in ['q','r']:
        if 'HTCondor' in config.batch:
          jobarg = str(job.args)
        else:
          if joblines is None:
            joblines = FileIO().read_lines(jobcfg['joblist'])
          jobarg = joblines[job.taskid-1]
        classifier.add_pending(job,jobarg)
  outfiles = storage.getfiles(filter=classifier.patterns,verb=verbosity-1) # get output files
  if skim:
    _classify_skims(classifier,outfiles,nexpected,checkevts,ncores,reporter,verbosity)
  else:
    _classify_trees(classifier,outfiles,nexpected,checkevts,reporter,verbosity)
  status = classifier.finish(nexpected,checkevts)

  # 4. REPORT
  for line in format_summary(status):
    reporter.line(line)
  if showlogs!=0 and (status.failed or status.missing):
    _report_logs(status,jobcfg,config,showlogs,reporter)

  return status


# ===== Observation loops =====

def _classify_skims(classifier,outfiles,nexpected,checkevts,ncores,reporter,verbosity):
  """Validate all skim outputs (in parallel), then assign each to its chunk."""
  bar = None # loading bar
  if verbosity<=1 and len(outfiles)>=15:
    status = "files, 0/%d events (0%%)"%(nexpected) if nexpected>0 else "files"
    bar = reporter.progress(len(outfiles),width=20,prefix=">>> Checking output files: ",
                            message=status,counter=True,remove=True)
  elif verbosity>=2:
    reporter.line(">>> %-12s = %s"%('pendchunks',classifier.pending))
    reporter.line(">>> %-12s = %s"%('outfiles',outfiles))
  validated = itervalid(outfiles,checkevts=checkevts,ncores=ncores,verb=verbosity) # get number of events processed & check for corruption
  for nevents, fname in validated: # use validator for parallel processing
    classifier.add_output(fname,nevents)
    if bar:
      nproc  = classifier.nprocevents
      status = "files, %s/%s events (%d%%)"%(nproc,nexpected,100.0*nproc/nexpected) if nexpected>0 else "files"
      bar.count(status)


def _classify_trees(classifier,outfiles,nexpected,checkevts,reporter,verbosity):
  """Assign each tree output to its chunk; validate only outputs of chunks that are not pending."""
  bar = None # loading bar
  if verbosity<=1 and len(outfiles)>=15:
    bar = reporter.progress(len(outfiles),width=20,prefix=">>> Checking output files: ",
                            message="files, 0/%d (0%%)"%(nexpected),counter=True,remove=True)
  elif verbosity>=2:
    reporter.line(">>> %-12s = %s"%('pendchunks',classifier.pending))
    reporter.line(">>> %-12s = %s"%('outfiles',outfiles))
  for fname in outfiles:
    if verbosity>=2:
      reporter.line(">>>   Checking job output '%s'..."%(fname))
    ichunk = classifier.accept(fname)
    if ichunk is None:
      continue
    nevents = isvalid(fname) if checkevts else 0 # get number of processed events & check for corruption
    classifier.add_output(ichunk,fname,nevents)
    if bar:
      nproc  = classifier.nprocevents
      status = "files, %s/%s events (%d%%)"%(nproc,nexpected,100.0*nproc/nexpected) if nexpected>0 else ""
      bar.count(status)


def _report_logs(status,jobcfg,config,showlogs,reporter):
  """Print the log file of each failed or missing chunk (looking back through earlier tries)."""
  cfgname  = jobcfg['config']
  jobids   = jobcfg['jobids']
  logglob  = os.path.join(jobcfg['logdir'],"*.*.*") #.log
  lognames = sorted(glob.glob(logglob),key=alphanum_key,reverse=True)
  chunkset = {j:None for j in jobids}
  chunkset[jobids[-1]] = jobcfg['chunks'] # current job ID
  maxlogs  = showlogs if showlogs>0 else len(status.failed)+len(status.missing)
  for chunk in sorted(status.failed+status.missing)[:maxlogs]:
    for i, jobid in enumerate(reversed(jobids)):
      chunks = chunkset[jobid]
      if chunks==None:
        oldtag  = "_try%d.json"%(jobcfg['try'])
        newtag  = "_try%d.json"%(jobcfg['try']-i)
        logname = cfgname.replace(oldtag,newtag)
        if not os.path.isfile(logname):
          reporter.warning("Did not find job config %r!"%(logname))
          continue
        with open(logname,'r') as file:
          oldjobcfg = json.load(file)
          chunks = oldjobcfg.get('chunks',[ ])
          chunkset[jobid] = chunks
      if chunks and chunk in chunks:
        taskid  = chunks.index(chunk)+(0 if 'HTCondor' in config.batch else 1)
        logexp  = "%d.%d.log"%(jobid,taskid)
        #logexp  = re.compile(".*\.\d{3,}\.%d(?:\.log)?$"%(taskid)) #$JOBNAME.$JOBID.$TASKID.log
        matches = [f for f in lognames if f.endswith(logexp)]
        if matches:
          reporter.line(">>>   %s"%(matches[0]))
          lognames.remove(matches[0])
          break
    else:
      reporter.warning("Did not find log file for chunk %d"%(chunk))


# ===== Classifiers =====

class _Classifier(object):
  """Shared state: chunk lists per state, processed events, and the chunks of the last try.
  Works on a copy of the job config's chunkdict; finish() returns the chunks to keep."""

  def finish(self,nexpected,checkevts):
    """Sort the chunk lists and return the ChunkStatus."""
    self._resubmission()
    for chunks in (self.good,self.pending,self.bad,self.missing):
      chunks.sort()
    return ChunkStatus(good=self.good,pending=self.pending,failed=self.bad,missing=self.missing,
                       nchunks=self.nchunks,nprocevents=self.nprocevents,nexpected=nexpected,checkevts=checkevts,
                       resubfiles=self.resubfiles,chunkdict=self.chunkdict)

  def _report_patterns(self,patterns,checkqueue,jobs):
    if self.verbosity>=2:
      for key, value in patterns:
        self.reporter.line(">>> %-12s = %r"%(key,value))
      self.reporter.line(">>> %-12s = %s"%('checkqueue',checkqueue))
      self.reporter.line(">>> %-12s = %s"%('pendjobs',jobs))
      self.reporter.line(">>> %-12s = %s"%('jobids',self.jobids))

  def __init__(self,jobcfg,filenevts,checkexpevts,reporter,verbosity):
    self.chunkdict    = dict(jobcfg['chunkdict']) # chunk -> input files; pruned to the chunks to keep
    self.cfgname      = jobcfg['config']
    self.jobids       = jobcfg['jobids']
    self.postfix      = jobcfg['postfix']
    self.filenevts    = filenevts
    self.checkexpevts = checkexpevts
    self.reporter     = reporter
    self.verbosity    = verbosity
    self.nchunks      = len(self.chunkdict) # = number of jobs
    self.good         = [ ] # good job output
    self.pending      = [ ] # pending or running jobs
    self.bad          = [ ] # corrupted job output
    self.missing      = [ ] # missing job output
    self.resubfiles   = [ ] # files to resubmit (if bad or missing)
    self.nprocevents  = 0   # total number of processed events


class _SkimClassifier(_Classifier):
  """nanoAOD skims: one or more output files per job, named after the input file (+ _N if split by events)."""

  def add_pending(self,job,jobarg):
    """A queued/running job: find its chunk from the input files in its arguments."""
    chunkdict = self.chunkdict
    matches   = self.flagexp.findall(jobarg)
    matches2  = self.flagexp2.findall(jobarg)
    if self.verbosity>=3:
      self.reporter.line(">>>   jobarg   = %s"%(jobarg.replace('\n','')))
      self.reporter.line(">>>   matches  = %s"%(matches))
      self.reporter.line(">>>   matches2 = %s"%(matches2))
    if not matches:
      return
    infiles = [ ]
    for file in matches[0].split():
      if not file.endswith('.root'):
        break
      if matches2:
        file += ":%s"%(matches2[0][0]) #,matches2[0][1])
      infiles.append(file)
    LOG.insist(infiles,"Did not find any ROOT files in job arguments %r, matches=%r"%(jobarg,matches))
    ichunk = -1
    for i in chunkdict:
      if all(any(f in c for c in chunkdict[i]) for f in infiles):
        ichunk = i
        break
    LOG.insist(ichunk>=0,
               "Did not find to which the input files of jobids %s belong! "%(self.jobids)+
               "\nichunk=%s,\ninfiles=%s,\nchunkdict=%s"%(ichunk,infiles,chunkdict))
    LOG.insist(len(chunkdict[i])==len(infiles),
               "Mismatch between input files of jobids %s and chunkdict! "%(self.jobids)+
               "\nichunk=%s,\ninfiles=%s,\nchunkdict[%s]=%s"%(ichunk,infiles,ichunk,chunkdict[ichunk]))
    self.pending.append(ichunk)

  def add_output(self,fname,nevents):
    """A validated output file (nevents<0: corrupted): find the input file and chunk it belongs to."""
    verbosity = self.verbosity
    filenevts = self.filenevts
    if verbosity>=2:
      self.reporter.line(">>>   Checking job output '%s'..."%(fname))
    basename = os.path.basename(fname)
    infile   = self.chunkexp.sub(r"\1.root",basename) # reconstruct input file without path or postfix
    outmatch = self.chunkexp.match(basename)
    ipart    = int(outmatch.group(2) or -1) if outmatch else -1 # >0 if input file split by events
    ichunk   = -1
    matches  = [ ] # count how many times matched to chunk (if split by events)
    for i in self.chunkdict:
      if ichunk>-1: # already found corresponding input file in the previous iteration
        break
      for chunkfile in self.chunkdict[i]: # find chunk output file belongs to
        if infile not in chunkfile: continue
        matches.append(i)
        nevtsexp  = -1
        inmatch   = evtsplitexp.match(chunkfile) # filename:firstevt:maxevts
        if inmatch: # chunk was split by events
          firstevt = int(inmatch.group(2))
          maxevts  = int(inmatch.group(3))
          if firstevt/maxevts!=ipart: # right file, wrong chunk
            if verbosity>=3:
              self.reporter.line(">>>   Not in chunk %d, %r"%(i,chunkfile))
            continue
          if self.checkexpevts or verbosity>=2:
            filentot = filenevts.get(inmatch.group(1),-1)
            if filentot>-1 and firstevt>=filentot: # sanity check
              self.reporter.warning("checkchunks: chunk %d has firstevt=%s>=%s=filentot, which indicates a bug or changed input file %s."%(
                ichunk,firstevt,filentot,chunkfile))
            nevtsexp = min(maxevts,filentot-firstevt) if filentot>-1 else maxevts # = maxevts; roughly expected nevts (some loss due to cuts)
        elif self.checkexpevts or verbosity>=2:
          nevtsexp = filenevts.get(chunkfile,-1) # expected number of processed events
        ichunk = i
        if ichunk in self.pending:
          if verbosity>=2:
            self.reporter.line(">>>   => Pending...")
          continue
        if nevents<0:
          if verbosity>=2:
            self.reporter.line(">>>   => Bad nevents=%s..."%(nevents))
          self.badfiles.append(chunkfile)
        else:
          if self.checkexpevts and nevtsexp>-1 and nevents!=nevtsexp:
            self.reporter.warning("checkchunks: Found %s processed events, but expected %s for %s..."%(nevents,nevtsexp,fname))
          if verbosity>=2:
            if nevtsexp>0:
              frac = "%.1f%%"%(100.0*nevents/nevtsexp) if nevtsexp!=0 else ""
              self.reporter.line(">>>   => Good, nevents=%s/%s %s"%(nevents,nevtsexp,frac))
            else:
              self.reporter.line(">>>   => Good, nevents=%s"%(nevents))
          self.nprocevents += nevents
          self.goodfiles.append(chunkfile)
    if verbosity>=2 and ichunk<0:
      if matches:
        self.reporter.line(">>>   => No match with input file (ipart=%d, but found in %d chunks; %s)..."%(ipart,len(matches),matches))
      else:
        self.reporter.line(">>>   => No match with input file...")

  def _resubmission(self):
    """Per chunk: all files good, or keep the good files and resubmit the bad (corrupted) or missing ones."""
    chunkdict = self.chunkdict
    for ichunk in list(chunkdict.keys()): # chuckdict length might be changed (popped)
      if ichunk in self.pending: # output still pending
        continue
      chunkfiles = chunkdict[ichunk]
      keepfiles  = [ ] # do not redo good files in this chunk
      bad        = False # count each chunk only once: bad, else missing
      for fname in chunkfiles: # check bad (corrupted) or missing
        LOG.insist(fname not in self.resubfiles,"Found file for chunk '%d' more than once: %s "%(ichunk,fname)+
                                                "Possible overcounting or conflicting job output file format! Check %s"%(self.cfgname))
        if fname in self.goodfiles: # good file, do not resubmit
          keepfiles.append(fname)
        else:
          bad = bad or fname in self.badfiles # bad (corrupted) or missing, resubmit
          self.resubfiles.append(fname)
      if len(keepfiles)==len(chunkfiles): # all files in this chunk were succesful
        self.good.append(ichunk)
      else:
        if len(keepfiles)==0: # all files bad or missing
          chunkdict.pop(ichunk) # remove chunk from chunkdict to allow for reshuffling
        else: # part of file list bad or missing
          chunkdict[ichunk] = keepfiles # keep record of good ones for bookkeeping, resubmit bad ones
        if bad:
          self.bad.append(ichunk)
        else:
          self.missing.append(ichunk)

  def report_settings(self,checkqueue,jobs):
    self._report_patterns([('flagexp',self.flagexp.pattern),('flagexp2',self.flagexp2.pattern),
                           ('fpatterns',self.patterns),('chunkexp',self.chunkexp.pattern)],checkqueue,jobs)

  def __init__(self,*args,**kwargs):
    super().__init__(*args,**kwargs)
    postfix       = self.postfix
    evtsplit      = any(any(evtsplitexp.match(f) for f in self.chunkdict[i]) for i in self.chunkdict)
    self.flagexp  = re.compile(r"-i (.+\.root)") #r"-i ((?:(?<! -).)+\.root[, ])"
    self.flagexp2 = re.compile(r"--firstevt (\d+) -m (\d+)")
    self.chunkexp = re.compile(r"(.+)%s(?:_(\d+))?\.root"%(postfix))
    self.patterns = ["*%s.root"%(postfix)] # storage filters of the output files
    if evtsplit:
      self.patterns.append("*%s_[0-9]*.root"%(postfix))
    self.goodfiles = [ ]
    self.badfiles  = [ ]


class _TreeClassifier(_Classifier):
  """Analysis (pico) trees: one output file per job, named *$POSTFIX_$CHUNK.root."""

  def add_pending(self,job,jobarg):
    """A queued/running job: its chunk number is in the -t argument."""
    matches = self.flagexp.findall(jobarg)
    if self.verbosity>=3:
      self.reporter.line(">>> jobarg = %r"%(jobarg))
      self.reporter.line(">>> matches = %s"%(matches))
    if not matches:
      return
    ichunk = int(matches[0])
    LOG.insist(ichunk in self.chunkdict,"Found an impossible chunk %d for job %s.%s! "%(ichunk,job.jobid,job.taskid)+
                                        "Possible overcounting!")
    self.pending.append(ichunk)

  def accept(self,fname):
    """Chunk number of an output file that should be validated; None if unknown or still pending."""
    match = self.chunkexp.search(fname)
    if not match:
      #LOG.warn("Did not recognize output file '%s'!"%(fname))
      return None
    ichunk = int(match.group(1))
    LOG.insist(ichunk in self.chunkdict,"Found an impossible chunk %d for file %s! Chunkdict has %s"%(ichunk,fname,list(sorted(self.chunkdict.keys())))+
                                        " Possible overcounting or conflicting job output file format! Check %s"%(self.cfgname))
    if ichunk in self.pending:
      return None
    return ichunk

  def add_output(self,ichunk,fname,nevents):
    """A validated output file of chunk ichunk (nevents<0: corrupted)."""
    verbosity = self.verbosity
    filenevts = self.filenevts
    if nevents<0:
      if verbosity>=2:
        self.reporter.line(">>>   => Bad, nevents=%s"%(nevents))
      self.bad.append(ichunk)
      # TODO: remove file from outdir to avoid conflicting output ?
    else:
      nevtsexp = 0 # expected number of processed events
      if self.checkexpevts or verbosity>=2:
        for chunkfile in self.chunkdict[ichunk]: # count events for each input file in this chunk
          inmatch = evtsplitexp.match(chunkfile) # look for filename:firstevt:maxevts
          if inmatch: # chunk was split by events
            firstevt  = int(inmatch.group(2))
            maxevts   = int(inmatch.group(3))
            filentot  = filenevts.get(inmatch.group(1),-1)
            if firstevt>=filentot: # sanity check
              self.reporter.warning("checkchunks: Chunk %d has firstevt=%s>=%s=filentot, which indicates a bug or changed input file %s."%(
                ichunk,firstevt,filentot,chunkfile))
            nevtsexp += min(maxevts,filentot-firstevt) if filentot>-1 else maxevts
          else:
            nevtsexp += filenevts.get(chunkfile,0)
        if self.checkexpevts and nevtsexp>0 and nevents!=nevtsexp:
          self.reporter.warning("checkchunks: Found %s processed events, but expected %s for %s..."%(nevents,nevtsexp,fname))
      if verbosity>=2:
        if nevtsexp>0:
          frac = "%.1f%%"%(100.0*nevents/nevtsexp) if nevtsexp!=0 else ""
          self.reporter.line(">>>   => Good, nevents=%d/%d %s"%(nevents,nevtsexp,frac))
        else:
          self.reporter.line(">>>   => Good, nevents=%s"%(nevents))
      self.nprocevents += nevents
      self.good.append(ichunk)

  def _resubmission(self):
    """Missing chunks are those without output; bad and missing chunks are resubmitted with all their files."""
    chunkdict = self.chunkdict
    if self.verbosity>=2:
      self.reporter.line(">>> %-12s = %s"%('nprocevents',self.nprocevents))
    for ichunk in list(chunkdict.keys()):
      count = self.good.count(ichunk)+self.pending.count(ichunk)+self.bad.count(ichunk)
      LOG.insist(count in [0,1],"Found %d times chunk '%d' (good=%d, pending=%d, bad=%d). "%(
                                count,ichunk,self.good.count(ichunk),self.pending.count(ichunk),self.bad.count(ichunk))+
                                "Possible overcounting or conflicting job output file format!")
      if count==0: # missing chunk
        self.missing.append(ichunk)
      elif ichunk not in self.bad: # good or pending chunk
        continue
      fchunk = chunkdict[ichunk]
      for fname in fchunk:
        LOG.insist(fname not in self.resubfiles,"Found file for chunk '%d' more than once: %s "%(ichunk,fname)+
                                                "Possible overcounting or conflicting job output file format!")
      self.resubfiles.extend(chunkdict[ichunk])
      chunkdict.pop(ichunk) # only save good chunks

  def report_settings(self,checkqueue,jobs):
    self._report_patterns([('flagexp',self.flagexp.pattern),('fpattern',self.patterns),
                           ('chunkexp',self.chunkexp.pattern)],checkqueue,jobs)

  def __init__(self,*args,**kwargs):
    super().__init__(*args,**kwargs)
    postfix       = self.postfix
    self.flagexp  = re.compile(r"-t \w*_(\d+)")
    self.patterns = "*%s_[0-9]*.root"%(postfix) # storage filter of the output files: _$postfix_$chunk
    self.chunkexp = re.compile(r".+%s_(\d+)\.root"%(postfix))


# ===== Result =====

@dataclass
class ChunkStatus:
  """Chunk numbers of a sample's last try per state, processed vs. expected events, and what to resubmit."""
  good:        list  # chunks with valid output
  pending:     list  # chunks with queued or running jobs
  failed:      list  # chunks with corrupted output
  missing:     list  # chunks without output
  nchunks:     int   # chunks in the last try
  nprocevents: int   # events in the valid output files
  nexpected:   int   # expected events (job config or DAS)
  checkevts:   bool  # output files were validated and their events counted
  resubfiles:  list  # input files to resubmit (of failed and missing chunks)
  chunkdict:   dict  # chunk -> input files that are done (kept on resubmission)

  @property
  def npending(self):
    return len(self.pending)

  @property
  def mergeable(self):
    """All chunks done: nothing to resubmit and nothing pending (the condition for hadd and cleanup)."""
    return not self.resubfiles and self.npending==0


def format_summary(status):
  """The SUCCESS/PEND/FAIL/MISS lines of a status (states without chunks are left out)."""
  rtext = ""
  if status.nexpected>0: # report number of processed events
    if status.checkevts:
      ratio = 100.0*status.nprocevents/status.nexpected
      rcol  = 'green' if ratio>90. else 'yellow' if ratio>80. else 'red'
      rtext = ": "+color("%d/%d events (%d%%)"%(status.nprocevents,status.nexpected,ratio),rcol,bold=True)
    else:
      rtext = ": expect %d events"%(status.nexpected)
  lines = [
    _summary_line(status.good,   status.nchunks,'SUCCESS',"Chunks with output in outdir"+rtext,'green'),
    _summary_line(status.pending,status.nchunks,'PEND',   "Chunks with pending or running jobs",'white',True),
    _summary_line(status.failed, status.nchunks,'FAIL',   "Chunks with corrupted output in outdir",'red',True),
    _summary_line(status.missing,status.nchunks,'MISS',   "Chunks with no output in outdir",'red',True),
  ]
  return [line for line in lines if line]


# ===== Helpers =====

def _summary_line(chunks,nchunks,label,text,col,show=False):
  """One summary line, or None without chunks. With show, list the chunks ('all A-B' if all of them)."""
  if not chunks:
    return None
  ratio = color("%4d/%d"%(len(chunks),nchunks),col,bold=False)
  label = color(label,col,bold=True)
  if not show: # do not print chunks
    jstr = ""
  elif len(chunks)==nchunks: # do not bother printing out full chunks list
    jstr = ": all %s-%s"%(chunks[0],chunks[-1])
  else: # list pending/failed/missing chunks
    jstr = (": "+', '.join(str(j) for j in chunks))
  return ">>> %s %s - %s%s"%(ratio,label,text,jstr)

