# Author: Izaak Neutelings (April 2020)
"""SGE batch system (Sun/Univa/Son of Grid Engine).

Submits one array job per task list with `qsub -t 1-N`; the template batch/templates/submit_SGE.sh runs
line $SGE_TASK_ID of the task list. Job states come from `qstat`, which does not show task arguments, so
status checks look the task up in the task list by its index (as for SLURM).

NOTE: rewritten in 2026 (BUGS.md S01): the previous class was a copy of the HTCondor adapter named
`HTCondor`, so `getbatch('SGE')` always failed. This implementation has not been run on an SGE site.

Public API:
  SGE(verb)   submit with qsub, query with qstat
"""

# ===== Imports =====
import os, re, getpass
from TauFW.PicoProducer.batch.base import BatchSystem, Job, JobList

__all__ = ['SGE']


# ===== Public API =====

class SGE(BatchSystem):
  # https://gridscheduler.sourceforge.net/htmlman/htmlman1/qsub.html

  def __init__(self,verb=False):
    super(SGE,self).__init__(verb=verb)
    # https://gridscheduler.sourceforge.net/htmlman/htmlman1/qstat.html
    self.statusdict = { 'q': ['qw','hqw','hRwq'], 'r': ['r','t','Rr','Rt'], 'f': ['Eqw','Ehqw','EhRqw','dr','dt'], 'c': [ ] }
    self.jobidrexp  = re.compile(r"Your job(?:-array)? (\d+)")
    self.user       = getpass.getuser()

  def statuscode(self,code):
    """Map a qstat state (e.g. 'qw', 'r', 'Eqw') to q/r/f/c, or '?'."""
    for skey, codelist in self.statusdict.items():
      if code in codelist:
        return skey
    return 'f' if 'E' in code else '?'

  def submit(self,script=None,taskfile=None,**kwargs):
    """Submit a script with some optional parameters. Return the job ID."""
    name      = kwargs.get('name',  None           )
    array     = kwargs.get('array', None           ) # number of tasks; default: number of lines in taskfile
    queue     = kwargs.get('queue', None           ) # queue: 'all.q','short.q','long.q'
    short     = kwargs.get('short', False          ) # run short test job
    time      = kwargs.get('time',  None           ) # e.g. 420, 04:20:00, 04:20
    logfile   = kwargs.get('log',   None           )
    options   = kwargs.get('opt',   None           )
    dry       = kwargs.get('dry',   False          )
    verbosity = kwargs.get('verb',  self.verbosity )
    failflags = ["error","denied"]
    jobids    = [ ]
    subcmd    = "qsub"
    if script==None:
      script = self.script
    if array==None and taskfile and os.path.isfile(taskfile):
      with open(taskfile,'r') as file:
        array = sum(1 for line in file if line.strip())
    if name:
      subcmd += " -N %s"%(name)
    if array:
      subcmd += " -t 1-%s"%(array)
    if short:
      if not queue: queue = "short.q" # shortest queue name might vary per system
      if not time:  time  = "00:06:00" # 6 minutes
    if queue:
      subcmd += " -q %s"%(queue)
    if time:
      if time.count(':')==0: # e.g. 420 seconds
        secs  = int(time)
        time  = "%02d:%02d:%02d"%(secs//3600,(secs%3600)//60,secs%60)
      elif time.count(':')==1: # e.g. 04:20
        time += ":00"
      subcmd += " -l h_rt=%s"%(time)
    if logfile:
      subcmd += " -o %s"%(logfile)
    if options:
      subcmd += " "+options
    subcmd += " "+script
    if taskfile:
      subcmd += " "+taskfile # list of tasks to be executed per job by submit_SGE.sh
    out = self.execute(subcmd,dry=dry,verb=verbosity)
    fail = False
    for line in out.split(os.linesep):
      if any(f in line.lower() for f in failflags):
        fail = True
      for match in self.jobidrexp.findall(line):
        jobids.append(int(match))
    if fail:
      print(">>> Warning! Submission failed!")
      print(out)
    jobid = jobids[0] if len(jobids)==1 else jobids if len(jobids)>1 else 0
    return jobid

  def queue(self,job,**kwargs):
    """Get queue status."""
    verbosity = kwargs.get('verb', self.verbosity )
    return self.execute("qstat -u %s"%(self.user),verb=verbosity)

  def status(self,job,**kwargs):
    """Check status of queued or running jobs."""
    verbosity = kwargs.get('verb', self.verbosity )
    return self.execute("qstat -j %s"%(job.jobid),fatal=False,verb=verbosity)

  def jobs(self,jobids=[],**kwargs):
    """Get job status, return JobList object.
    qstat columns: job-ID prior name user state submit/start-date time [queue] [slots] [ja-task-ID]"""
    if not isinstance(jobids,list):
      jobids  = [jobids]
    verbosity = kwargs.get('verb', self.verbosity )
    jobids    = [str(j) for j in jobids]
    rows      = self.execute("qstat -u %s"%(self.user),fatal=False,verb=verbosity)
    jobs      = JobList([ ])
    for row in rows.split('\n'):
      values = row.split()
      if len(values)<7 or not values[0].isdigit():
        continue # header or separator
      jobid = values[0]
      if jobids and jobid not in jobids:
        continue
      status = self.statuscode(values[4])
      tasks  = values[-1] if len(values)>=9 else "" # e.g. '3' or '1-10:1' for pending ranges
      match  = re.match(r"(\d+)(?:-(\d+)(?::(\d+))?)?$",tasks)
      if match:
        first = int(match.group(1))
        last  = int(match.group(2) or first)
        step  = int(match.group(3) or 1)
        taskids = list(range(first,last+1,step))
      else:
        taskids = [-1]
      for taskid in taskids:
        if verbosity>=3:
          print(">>> %10s %10s %8s %8s"%(values[3],jobid,taskid,status))
        jobs.append(Job(self,jobid,taskid=taskid,status=status))
    return jobs

