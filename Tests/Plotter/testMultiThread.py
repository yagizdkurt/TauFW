#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Izaak Neutelings (Februari 2019)
from TauFW.Utilities.Drawing import LOG
from TauFW.Utilities.Process import ParallelProcessor
from ROOT import gROOT, gSystem, gDirectory, TFile, TH1D
import time


def foo(i,bar,**kwargs):
  """Simple test function to be multithreaded."""
  if kwargs:
    print('foo %d says "%s", with extra options: %s'%(i,bar,kwargs))
  else:
    print('foo %d says "%s"'%(i,bar))
  time.sleep(2)
  #for i in range(100000):
  #  pass
  result = i**2
  return result
  

def draw(histname,filename):
  """Simple test function to be multithreaded."""
  #print ">>> Drawing %s..."%histname
  #filename = "/scratch/ineuteli/analysis/LQ_2018/SingleMuon/SingleMuon_Run2018_mutau.root"
  file = TFile.Open(filename)
  tree = file.Get('tree')
  hist = TH1D(histname,histname,100,0,200)
  tree.Draw("m_vis >> %s"%histname,"",'gOff') #getFakeRate(pt_2,m_2,eta_2,decayMode_2)
  print(">>> Drawing %s... %s"%(histname,hist))
  #gDirectory.Delete(histname)
  hist.SetDirectory(0)
  file.Close()
  return hist
  

def testProcess(N=5):
  """Test multiprocessing behavior."""
  LOG.header("testProcess")
  
  print(">>> Sequential:")
  start = time.time()
  for i in range(1,N+1):
    name = "thread %d"%i
    result = foo(i,"Hello world!")
    print(">>>   thread %s returns: %r"%(i,result))
  print(">>> Took %.1f seconds"%(time.time()-start))
  
  print("\n>>> Parallel:")
  start = time.time()
  threads = [ ]
  for i in range(1,N+1):
    name   = "thread %d"%i
    thread = Process(target=foo,args=(i,"Hello world!"))
    thread.start()
    threads.append(thread)
  for thread in threads:
    result = thread.join()
    print(">>>   %s returns: %r"%(thread.name,result))
  print(">>> Took %.1f seconds"%(time.time()-start))
  print('')
  

def testMultiProcessor(N=5):
  """Test multiprocessing behavior."""
  LOG.header("testParallelProcessor")
  
  print(">>> Sequential:")
  start = time.time()
  for i in range(1,N+1):
    result = foo(i,"Hello world!")
    print(">>>   thread %s returns: %r"%(i,result))
  print(">>> Took %.1f seconds"%(time.time()-start))
  
  print("\n>>> Parallel:")
  start = time.time()
  processor = ParallelProcessor()
  for i in range(1,N+1):
    name = "process %d"%i
    processor.start(target=foo,args=(i,"Hello world!"),name=name)
  for process in processor:
    result = process.join() # wait for processes to end
    print(">>>   %s returns: %r"%(process.name,result))
  print(">>> Took %.1f seconds"%(time.time()-start))
  print('')
  

def testMultiProcessorWithDraw(filename,N=5):
  """Test multiprocessing behavior with TTree:Draw."""
  LOG.header("testParallelProcessorWithDraw")
  
  print(">>> Sequential:")
  start = time.time()
  for i in range(1,N+1):
   name = "thread_%d"%i
   result = draw(name,filename)
   print(">>>   %s returns: %r"%(name,result))
  print(">>> Took %.1f seconds"%(time.time()-start))
  
  print("\n>>> Parallel:")
  start = time.time()
  processor = ParallelProcessor()
  for i in range(1,N+1):
    name = "process_%d"%i
    processor.start(target=draw,args=(name,filename),name=name)
  for process in processor:
    result = process.join() # wait for processes to end
    print(">>>   %s returns: %r"%(process.name,result))
    #result.Delete() # segmentation fault?
  print(">>> Took %.1f seconds"%(time.time()-start))
  print('')
  

def main(args):
  """Main function."""
  N = 5
  #filename = "/scratch/ineuteli/analysis/LQ_2018/SingleMuon/SingleMuon_Run2018_mutau.root"
  filename = "/eos/user/i/ineuteli/analysis/g-2/UL2018/Data/SingleMuon_Run2018B_mumu.root"
  filename = args.filename or filename
  #testProcess(N)
  testMultiProcessor(N)
  testMultiProcessorWithDraw(filename,N=N)
  

if __name__ == '__main__':
  from argparse import ArgumentParser
  description = """Test ParallelProcessor (TauFW.Utilities.Process)."""
  parser = ArgumentParser(prog="testMultiThread",description=description,epilog="Good luck!")
  parser.add_argument('filename', nargs='?', help="filename to run over in parallel" )
  args = parser.parse_args()
  main(args)
  print(">>> Done!")
  
