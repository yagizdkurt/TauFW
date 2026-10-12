# Author: Izaak Neutelings (April 2020)
"""Status of a sample's jobs: which chunks succeeded, are pending, failed (corrupted output) or are missing.

Moved unchanged from pico/job.py (Part 4A-2). Part 4A-3 splits it into the observation steps (queue, storage
listing, file validation) and a pure classifier, and routes its output through a reporter.

Inputs:  a Sample loaded from its job config (getcfgsamples), the configuration, the batch queue,
         and the output files in storage.
Outputs: the SUCCESS/PEND/FAIL/MISS summary lines (printed); (files to resubmit, chunkdict of good chunks,
         number of pending chunks).

Public API:
  checkchunks(sample, config, **kwargs)   -> (resubfiles, chunkdict, npending)
"""

# ===== Imports =====
import os, re, glob, json
from TauFW.common.tools.file import getline
from TauFW.common.tools.string import alphanum_key
from TauFW.common.tools.LoadingBar import LoadingBar
from TauFW.common.tools.log import Logger, color
from TauFW.PicoProducer.batch.factory import getbatch
from TauFW.PicoProducer.jobs.chunking import evtsplitexp
from TauFW.PicoProducer.storage.factory import getstorage
from TauFW.PicoProducer.storage.validation import isvalid, itervalid

__all__ = ['checkchunks']


# ===== Constants =====
LOG = Logger()


# ===== Status =====

def checkchunks(sample,config,**kwargs):
  """Help function to check jobs status: success, pending, failed or missing.
  Return list of files to be resubmitted, and a dictionary between chunk index and input files.
  Updates sample.jobcfg in place: 'nevents' (with das=True) and 'chunkdict' (good chunks only)."""
  outdir       = kwargs.get('outdir',       None  )
  channel      = kwargs.get('channel',      None  )
  tag          = kwargs.get('tag',          None  )
  checkqueue   = kwargs.get('checkqueue',   -1    ) # check queue of batch system for pending jobs
  checkevts    = kwargs.get('checkevts',    True  ) # validate output file & count events (slow, default)
  checkexpevts = kwargs.get('checkexpevts', False ) # compare actual to expected number of processed events
  pendjobs     = kwargs.get('jobs',         None  )
  checkdas     = kwargs.get('das',          True  ) # check number of events from DAS
  showlogs     = kwargs.get('showlogs',     False ) # print log files of failed jobs for debugging
  ncores       = kwargs.get('ncores',       4     ) # validate files in parallel
  verbosity    = kwargs.get('verb',         0     )
  oldjobcfg    = sample.jobcfg # job config from last job
  oldcfgname   = oldjobcfg['config']
  chunkdict    = oldjobcfg['chunkdict'] # filenames
  jobids       = oldjobcfg['jobids']
  joblist      = oldjobcfg['joblist']
  postfix      = oldjobcfg['postfix']
  logdir       = oldjobcfg['logdir']
  nfilesperjob = oldjobcfg['nfilesperjob']
  filenevts    = sample.filenevts
  if outdir==None:
    outdir     = oldjobcfg['outdir']
  storage      = getstorage(outdir,ensure=True) # StorageElement instance of output directory
  if channel==None:
    channel    = oldjobcfg['channel']
  if tag==None:
    tag        = oldjobcfg['tag']
  if not filenevts:
    checkexpevts==False
  elif checkexpevts==None:
    checkexpevts = 'skim' not in channel.lower() # default for pico analysis jobs
  evtsplit     = any(any(evtsplitexp.match(f) for f in chunkdict[i]) for i in chunkdict)
  noldchunks   = len(chunkdict) # = number of jobs
  goodchunks   = [ ] # good job output
  pendchunks   = [ ] # pending or running jobs
  badchunks    = [ ] # corrupted job output
  misschunks   = [ ] # missing job output
  resubfiles   = [ ] # files to resubmit (if bad or missing)
  
  # NUMBER OF EVENTS
  nprocevents = 0   # total number of processed events
  ndasevents  = oldjobcfg['nevents'] # total number of available events
  if checkdas: #and ndasevents==0: # get nevents straight from DAS
    ndasevents = sample.getnevents(das=True)
    oldjobcfg['nevents'] = ndasevents
  elif verbosity>=2:
    print(">>> %-12s = %s"%('ndasevents',ndasevents))
  if verbosity>=3:
    print(">>> %-12s = %s"%('chunkdict',chunkdict))
    print(">>> %-12s = %s"%('ncores',ncores))
  
  # CHECK PENDING JOBS
  if checkqueue<0 or pendjobs:
    if checkqueue!=1 or not pendjobs:
      batch = getbatch(config,verb=verbosity)
      pendjobs = batch.jobs(jobids,verb=verbosity-1) # refresh job list
    elif pendjobs:
      pendjobs = [j for j in pendjobs if j.jobid in jobids] # get new job list with right job id
  
  ###########################################################################
  # CHECK SKIMMED OUTPUT: nanoAOD format, one or more output files per job
  if 'skim' in channel.lower(): # and nfilesperjob>1:
    flagexp   = re.compile(r"-i (.+\.root)") #r"-i ((?:(?<! -).)+\.root[, ])"
    flagexp2  = re.compile(r"--firstevt (\d+) -m (\d+)")
    chunkexp  = re.compile(r"(.+)%s(?:_(\d+))?\.root"%(postfix))
    fpatterns = ["*%s.root"%(postfix)]
    if evtsplit:
      fpatterns.append("*%s_[0-9]*.root"%(postfix))
    if verbosity>=2:
      print(">>> %-12s = %r"%('flagexp',flagexp.pattern))
      print(">>> %-12s = %r"%('flagexp2',flagexp2.pattern))
      print(">>> %-12s = %r"%('fpatterns',fpatterns))
      print(">>> %-12s = %r"%('chunkexp',chunkexp.pattern))
      print(">>> %-12s = %s"%('checkqueue',checkqueue))
      print(">>> %-12s = %s"%('pendjobs',pendjobs))
      print(">>> %-12s = %s"%('jobids',jobids))
    
    # CHECK PENDING JOBS
    pendfiles = [ ]
    if pendjobs:
      for job in pendjobs:
        if verbosity>=3:
          print(">>> Found job %r, status=%r, args=%r"%(job,job.getstatus(),job.args.rstrip()))
        if job.getstatus() in ['q','r']:
          if 'HTCondor' in config.batch:
            jobarg   = str(job.args)
            matches  = flagexp.findall(jobarg)
            matches2 = flagexp2.findall(jobarg)
          else:
            jobarg   = getline(joblist,job.taskid-1)
            matches  = flagexp.findall(jobarg)
            matches2 = flagexp2.findall(jobarg)
          if verbosity>=3:
            print(">>>   jobarg   =",jobarg.replace('\n',''))
            print(">>>   matches  =",matches)
            print(">>>   matches2 =",matches2)
          if not matches:
            continue
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
                     "Did not find to which the input files of jobids %s belong! "%(jobids)+
                     "\nichunk=%s,\ninfiles=%s,\nchunkdict=%s"%(ichunk,infiles,chunkdict))
          LOG.insist(len(chunkdict[i])==len(infiles),
                     "Mismatch between input files of jobids %s and chunkdict! "%(jobids)+
                     "\nichunk=%s,\ninfiles=%s,\nchunkdict[%s]=%s"%(ichunk,infiles,ichunk,chunkdict[ichunk]))
          pendchunks.append(ichunk)
    
    # CHECK OUTPUT FILES
    outfiles  = storage.getfiles(filter=fpatterns,verb=verbosity-1) # get output files
    badfiles  = [ ]
    goodfiles = [ ]
    bar       = None # loading bar
    if verbosity<=1 and len(outfiles)>=15:
      status = "files, 0/%d events (0%%)"%(ndasevents) if ndasevents>0 else "files"
      bar = LoadingBar(len(outfiles),width=20,pre=">>> Checking output files: ",
                       message=status,counter=True,remove=True)
    elif verbosity>=2:
      print(">>> %-12s = %s"%('pendchunks',pendchunks))
      print(">>> %-12s = %s"%('outfiles',outfiles))
    validated = itervalid(outfiles,checkevts=checkevts,ncores=ncores,verb=verbosity) # get number of events processed & check for corruption
    for nevents, fname in validated: # use validator for parallel processing
      if verbosity>=2:
        print(">>>   Checking job output '%s'..."%(fname))
      basename = os.path.basename(fname)
      infile   = chunkexp.sub(r"\1.root",basename) # reconstruct input file without path or postfix
      outmatch = chunkexp.match(basename)
      ipart    = int(outmatch.group(2) or -1) if outmatch else -1 # >0 if input file split by events
      ichunk   = -1
      matches  = [ ] # count how many times matched to chunk (if split by events)
      for i in chunkdict:
        if ichunk>-1: # already found corresponding input file in the previous iteration
          break
        for chunkfile in chunkdict[i]: # find chunk output file belongs to
          if infile not in chunkfile: continue
          matches.append(i)
          nevtsexp  = -1
          inmatch   = evtsplitexp.match(chunkfile) # filename:firstevt:maxevts
          if inmatch: # chunk was split by events
            firstevt = int(inmatch.group(2))
            maxevts  = int(inmatch.group(3))
            if firstevt/maxevts!=ipart: # right file, wrong chunk
              if verbosity>=3:
                print(">>>   Not in chunk %d, %r"%(i,chunkfile))
              continue
            if checkexpevts or verbosity>=2:
              filentot = filenevts.get(inmatch.group(1),-1)
              if filentot>-1 and firstevt>=filentot: # sanity check
                LOG.warn("checkchunks: chunk %d has firstevt=%s>=%s=filentot, which indicates a bug or changed input file %s."%(
                  ichunk,firstevt,filentot,chunkfile))
              nevtsexp = min(maxevts,filentot-firstevt) if filentot>-1 else maxevts # = maxevts; roughly expected nevts (some loss due to cuts)
          elif checkexpevts or verbosity>=2:
            nevtsexp = filenevts.get(chunkfile,-1) # expected number of processed events
          ichunk = i
          if ichunk in pendchunks:
            if verbosity>=2:
              print(">>>   => Pending...")
            continue
          if nevents<0:
            if verbosity>=2:
              print(">>>   => Bad nevents=%s..."%(nevents))
            badfiles.append(chunkfile)
          else:
            if checkexpevts and nevtsexp>-1 and nevents!=nevtsexp:
              LOG.warn("checkchunks: Found %s processed events, but expected %s for %s..."%(nevents,nevtsexp,fname))
            if verbosity>=2:
              if nevtsexp>0:
                frac = "%.1f%%"%(100.0*nevents/nevtsexp) if nevtsexp!=0 else ""
                print(">>>   => Good, nevents=%s/%s %s"%(nevents,nevtsexp,frac))
              else:
                print(">>>   => Good, nevents=%s"%(nevents))
            nprocevents += nevents
            goodfiles.append(chunkfile)
      if verbosity>=2:
        if ichunk<0:
          if matches:
            print(">>>   => No match with input file (ipart=%d, but found in %d chunks; %s)..."%(ipart,len(matches),matches))
          else:
            print(">>>   => No match with input file...")
        #LOG.warn("Did not recognize output file '%s'!"%(fname))
        continue
      if bar:
        status = "files, %s/%s events (%d%%)"%(nprocevents,ndasevents,100.0*nprocevents/ndasevents) if ndasevents>0 else "files"
        bar.count(status)
    
    # GET FILES for RESUBMISSION + sanity checks
    for ichunk in list(chunkdict.keys()): # chuckdict length might be changed (popped)
      if ichunk in pendchunks: # output still pending
        continue
      chunkfiles = chunkdict[ichunk]
      keepfiles  = [ ] # do not redo good files in this chunk
      bad        = False # count each chunk only once: bad, else missing
      for fname in chunkfiles: # check bad (corrupted) or missing
        LOG.insist(fname not in resubfiles,"Found file for chunk '%d' more than once: %s "%(ichunk,fname)+
                                           "Possible overcounting or conflicting job output file format! Check %s"%(oldcfgname))
        if fname in goodfiles: # good file, do not resubmit
          keepfiles.append(fname)
        else:
          bad = bad or fname in badfiles # bad (corrupted) or missing, resubmit
          resubfiles.append(fname)
      if len(keepfiles)==len(chunkfiles): # all files in this chunk were succesful
        goodchunks.append(ichunk)
      else:
        if len(keepfiles)==0: # all files bad or missing
          chunkdict.pop(ichunk) # remove chunk from chunkdict to allow for reshuffling
        else: # part of file list bad or missing
          chunkdict[ichunk] = keepfiles # keep record of good ones for bookkeeping, resubmit bad ones
        if bad:
          badchunks.append(ichunk)
        else:
          misschunks.append(ichunk)
  
  
  ###########################################################################
  # CHECK ANALYSIS OUTPUT: custom tree format, one output file per job, numbered post-fix
  else:
    flagexp    = re.compile(r"-t \w*_(\d+)")
    fpattern   = "*%s_[0-9]*.root"%(postfix) # _$postfix_$chunk
    chunkexp   = re.compile(r".+%s_(\d+)\.root"%(postfix))
    if verbosity>=2:
      print(">>> %-12s = %r"%('flagexp',flagexp.pattern))
      print(">>> %-12s = %r"%('fpattern',fpattern))
      print(">>> %-12s = %r"%('chunkexp',chunkexp.pattern))
      print(">>> %-12s = %s"%('checkqueue',checkqueue))
      print(">>> %-12s = %s"%('pendjobs',pendjobs))
      print(">>> %-12s = %s"%('jobids',jobids))
    
    # CHECK PENDING JOBS
    if pendjobs:
      for job in pendjobs:
        if verbosity>=3:
          print(">>> Found job %r, status=%r, args=%r"%(job,job.getstatus(),job.args.rstrip()))
        if job.getstatus() in ['q','r']:
          if 'HTCondor' in config.batch:
            jobarg  = str(job.args)
            matches = flagexp.findall(jobarg)
          else:
            jobarg  = getline(joblist,job.taskid-1)
            matches = flagexp.findall(jobarg)
          if verbosity>=3:
            print(">>> jobarg = %r"%(jobarg))
            print(">>> matches = %s"%(matches))
          if not matches:
            continue
          ichunk = int(matches[0])
          LOG.insist(ichunk in chunkdict,"Found an impossible chunk %d for job %s.%s! "%(ichunk,job.jobid,job.taskid)+
                                         "Possible overcounting!")
          pendchunks.append(ichunk)
    
    # CHECK OUTPUT FILES
    outfiles = storage.getfiles(filter=fpattern,verb=verbosity-1) # get output files
    bar      = None # loading bar
    if verbosity<=1 and len(outfiles)>=15:
      bar = LoadingBar(len(outfiles),width=20,pre=">>> Checking output files: ",
                       message="files, 0/%d (0%%)"%(ndasevents),counter=True,remove=True)
    elif verbosity>=2:
      print(">>> %-12s = %s"%('pendchunks',pendchunks))
      print(">>> %-12s = %s"%('outfiles',outfiles))
    for fname in outfiles:
      if verbosity>=2:
        print(">>>   Checking job output '%s'..."%(fname))
      match = chunkexp.search(fname)
      if match:
        ichunk = int(match.group(1))
        LOG.insist(ichunk in chunkdict,"Found an impossible chunk %d for file %s! Chunkdict has %s"%(ichunk,fname,list(sorted(chunkdict.keys())))+
                                       " Possible overcounting or conflicting job output file format! Check %s"%(oldcfgname))
        if ichunk in pendchunks:
          continue
      else:
        #LOG.warn("Did not recognize output file '%s'!"%(fname))
        continue
      nevents = isvalid(fname) if checkevts else 0 # get number of processed events & check for corruption
      if nevents<0:
        if verbosity>=2:
          print(">>>   => Bad, nevents=%s"%(nevents))
        badchunks.append(ichunk)
        # TODO: remove file from outdir to avoid conflicting output ?
      else:
        nevtsexp = 0 # expected number of processed events
        if checkexpevts or verbosity>=2:
          for chunkfile in chunkdict[ichunk]: # count events for each input file in this chunk
            inmatch = evtsplitexp.match(chunkfile) # look for filename:firstevt:maxevts
            if inmatch: # chunk was split by events
              firstevt  = int(inmatch.group(2))
              maxevts   = int(inmatch.group(3))
              filentot  = filenevts.get(inmatch.group(1),-1)
              if firstevt>=filentot: # sanity check
                LOG.warn("checkchunks: Chunk %d has firstevt=%s>=%s=filentot, which indicates a bug or changed input file %s."%(
                  ichunk,firstevt,filentot,chunkfile))
              nevtsexp += min(maxevts,filentot-firstevt) if filentot>-1 else maxevts
            else:
              nevtsexp += filenevts.get(chunkfile,0)
          if checkexpevts and nevtsexp>0 and nevents!=nevtsexp:
            LOG.warn("checkchunks: Found %s processed events, but expected %s for %s..."%(nevents,nevtsexp,fname))
        if verbosity>=2:
          if nevtsexp>0:
            frac = "%.1f%%"%(100.0*nevents/nevtsexp) if nevtsexp!=0 else ""
            print(">>>   => Good, nevents=%d/%d %s"%(nevents,nevtsexp,frac))
          else:
            print(">>>   => Good, nevents=%s"%(nevents))
        nprocevents += nevents
        goodchunks.append(ichunk)
      if bar:
        status = "files, %s/%s events (%d%%)"%(nprocevents,ndasevents,100.0*nprocevents/ndasevents) if ndasevents>0 else ""
        bar.count(status)
    
    # GET FILES for RESUBMISSION + sanity checks
    if verbosity>=2:
      print(">>> %-12s = %s"%('nprocevents',nprocevents))
    for ichunk in list(chunkdict.keys()):
      count = goodchunks.count(ichunk)+pendchunks.count(ichunk)+badchunks.count(ichunk)
      LOG.insist(count in [0,1],"Found %d times chunk '%d' (good=%d, pending=%d, bad=%d). "%(
                                count,ichunk,goodchunks.count(ichunk),pendchunks.count(ichunk),badchunks.count(ichunk))+
                                "Possible overcounting or conflicting job output file format!")
      if count==0: # missing chunk
        misschunks.append(ichunk)
      elif ichunk not in badchunks: # good or pending chunk
        continue
      fchunk = chunkdict[ichunk]
      for fname in fchunk:
        LOG.insist(fname not in resubfiles,"Found file for chunk '%d' more than once: %s "%(ichunk,fname)+
                                           "Possible overcounting or conflicting job output file format!")
      resubfiles.extend(chunkdict[ichunk])
      chunkdict.pop(ichunk) # only save good chunks
  
  ###########################################################################
  
  # print(CHUNKS)
  goodchunks.sort()
  pendchunks.sort()
  badchunks.sort()
  misschunks.sort()
  def printchunks(jobden,label,text,col,show=False):
   if jobden:
     ratio = color("%4d/%d"%(len(jobden),noldchunks),col,bold=False)
     label = color(label,col,bold=True)
     if not show: # do not print chunks
       jstr = ""
     elif len(jobden)==noldchunks:# do not bother printing out full chunks list
       jobden.sort()
       jstr = ": all %s-%s"%(jobden[0],jobden[-1])
     else: # list pending/failed/missing chunks
       jstr = (": "+', '.join(str(j) for j in jobden))
     print(">>> %s %s - %s%s"%(ratio,label,text,jstr))
   #else:
   #  print(">>> %2d/%d %s - %s"%(len(jobden),len(jobs),label,text))
  rtext = ""
  if ndasevents>0: # report number of processed events
    if checkevts:
      ratio = 100.0*nprocevents/ndasevents
      rcol  = 'green' if ratio>90. else 'yellow' if ratio>80. else 'red'
      rtext = ": "+color("%d/%d events (%d%%)"%(nprocevents,ndasevents,ratio),rcol,bold=True)
    else:
      rtext = ": expect %d events"%(ndasevents)
  printchunks(goodchunks,'SUCCESS', "Chunks with output in outdir"+rtext,'green')
  printchunks(pendchunks,'PEND',"Chunks with pending or running jobs",'white',True)
  printchunks(badchunks, 'FAIL', "Chunks with corrupted output in outdir",'red',True)
  printchunks(misschunks,'MISS',"Chunks with no output in outdir",'red',True)
  
  # print(LOG FILES for debugging)
  if showlogs!=0 and (badchunks or misschunks):
    logglob  = os.path.join(logdir,"*.*.*") #.log
    lognames = sorted(glob.glob(logglob),key=alphanum_key,reverse=True)
    chunkset = {j:None for j in jobids}
    chunkset[jobids[-1]] = oldjobcfg['chunks'] # current job ID
    maxlogs  = showlogs if showlogs>0 else len(badchunks)+len(misschunks)
    for chunk in sorted(badchunks+misschunks)[:maxlogs]:
      for i, jobid in enumerate(reversed(jobids)):
        chunks = chunkset[jobid]
        if chunks==None:
          oldtag  = "_try%d.json"%(oldjobcfg['try'])
          newtag  = "_try%d.json"%(oldjobcfg['try']-i)
          logname = oldcfgname.replace(oldtag,newtag)
          if not os.path.isfile(logname):
            LOG.warn("Did not find job config %r!"%(logname))
            continue
          with open(logname,'r') as file:
            jobcfg = json.load(file)
            chunks = jobcfg.get('chunks',[ ])
            chunkset[jobid] = chunks
        if chunks and chunk in chunks:
          taskid  = chunks.index(chunk)+(0 if 'HTCondor' in config.batch else 1)
          logexp  = "%d.%d.log"%(jobid,taskid)
          #logexp  = re.compile(".*\.\d{3,}\.%d(?:\.log)?$"%(taskid)) #$JOBNAME.$JOBID.$TASKID.log
          matches = [f for f in lognames if f.endswith(logexp)]
          if matches:
            print(">>>   %s"%(matches[0]))
            lognames.remove(matches[0])
            break
      else:
        LOG.warn("Did not find log file for chunk %d"%(chunk))
  
  return resubfiles, chunkdict, len(pendchunks)
  
