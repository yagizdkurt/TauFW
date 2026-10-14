# =============================================================================
# LEGACY CODE - POSTFIT
# Original location: Fitter/TauID/takeZmu.py
# Previous archive: Fitter/Legacy/TauID/takeZmu.py
# Data-taking year: 2018
# Year basis: Explicit year setting is UL2018.
# Purpose: Attempts to extract ZTT_mu values from UL2018 fit logs across tau working points
#          and momentum bins.
# Why legacy: Unreferenced and has invalid indentation; it also prints dm although the loop
#             assigning it is commented out. No replacement is recorded.
# Status: Reference material; review dependencies and input paths before reuse.
# =============================================================================

year="UL2018"
jobdir='./log'
for wp in ['VVVLoose', 'VVLoose', 'VLoose', 'Loose', 'Medium', 'Tight', 'VTight', 'VVTight']:
       for pt in ["20to25", "25to30", "30to35", "35to40", "40to50", "50to70", "70to2000"] :
       print(wp)
       #for dm in ['dm0','dm1', 'dm10', 'dm11']:
           print(dm)
           file = open(jobdir + '/ztt_'+wp+'_'+year+'_pt'+pt+'.log')
           #file = open(jobdir + '/ztt_'+wp+'_'+year+'_'+dm+'.log')
           for line in file:
               line = line.rstrip()
               words = line.split()
               if line.find('ZTT_mu')!=-1:
                  val = float(words[2])
                  #print("WP: "+ wp + ", pT:"+pt+", Val=" + str(val))
                  print(val)


       print(' ')
       print(' ')
       print(' ')
       print(' ')
