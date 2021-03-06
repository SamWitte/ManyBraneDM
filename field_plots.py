import os
import numpy as np
from scipy.interpolate import interp1d
import matplotlib
matplotlib.use('Agg')
import pylab as pl
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
import matplotlib as mpl
import matplotlib.patheffects as PathEffects
import matplotlib.gridspec as gridspec
import glob
from matplotlib import rc
rc('font',**{'family':'serif','serif':['Times','Palatino']})
rc('text', usetex=True)


mpl.rcParams['xtick.major.size']=8
mpl.rcParams['ytick.major.size']=8
mpl.rcParams['xtick.labelsize']=18
mpl.rcParams['ytick.labelsize']=18

kval = 0.1
Nbrane = 1e7
pressFac = 1e-6
eCDM = 0.00

Fname = 'StandardUniverse_FieldEvolution_{:.4e}.dat'.format(kval)
Svname = 'StandardField_kval_{:.4e}.pdf'.format(kval)

#Fname = 'MultiBrane_FieldEvolution_{:.4e}_Nbrane_{:.0e}_PressFac_{:.2e}_eCDM_{:.2e}.dat'.format(kval, Nbrane, pressFac, eCDM)
#Svname = 'MultiverseField_kval_{:.4e}_Nbrane_{:.0e}_PressFac_{:.2e}_eCDM_{:.2e}.pdf'.format(kval, Nbrane, pressFac, eCDM)

path = os.getcwd()

pl.figure()
ax = pl.gca()

file = np.loadtxt(path + '/OutputFiles/' + Fname)

time_table = np.loadtxt(path+'/precomputed/Times_Tables.dat')
ct_to_scale = interp1d(np.log10(time_table[:,2]), np.log10(time_table[:,1]), kind='linear',
                                    bounds_error=False, fill_value='extrapolate')
scale_to_ct = interp1d(np.log10(time_table[:,1]), np.log10(time_table[:,2]), kind='linear',
                                    bounds_error=False, fill_value='extrapolate')
a_facts = np.zeros_like(file[:,0])
for i in range(len(a_facts)):
    a_facts[i] = 10.**ct_to_scale(np.log10(file[i,0]))


pl.plot(a_facts, np.abs(file[:,1]), 'b', lw=1, label='$\Phi$')
pl.plot(a_facts, np.abs(file[:,2]), 'r', lw=1, label='$\delta$')
pl.plot(a_facts, np.abs(file[:,3]), 'g', lw=1, label='$u$')
pl.plot(a_facts, np.abs(file[:,4]), 'c', lw=1, label='$\delta_b$')
pl.plot(a_facts, np.abs(file[:,5]), 'm', lw=1, label='$u_b$')
pl.plot(a_facts, np.abs(file[:,6]), 'k', lw=1, label='$\Theta_0$')
pl.plot(a_facts, np.abs(file[:,9]), 'y', lw=1, label='$\Theta_1$')
pl.plot(a_facts, np.abs(file[:,12]), '-g', lw=1, label='$\Theta_2$')
pl.plot(a_facts, np.abs(file[:,8]), 'maroon', lw=1, label='$N_0$')
pl.plot(a_facts, np.abs(file[:,11]), 'mediumslateblue', lw=1, label='$N_1$')
pl.plot(a_facts, np.abs(file[:,14]), 'dodgerblue', lw=1, label='$N_2$')
pl.plot(a_facts, np.abs(file[:,-1]), 'k-', lw=1, label='$\Psi$')
#pl.plot(a_facts, np.abs(file[:,15]), 'r', lw=1, label='$\Theta_3$')
#pl.plot(a_facts, np.abs(file[:,17]), 'r.', lw=1, label='$N_3$')


plt.tight_layout()
plt.legend(loc=1, frameon=True, framealpha=0.5, fontsize=9, ncol=1, fancybox=False)
plt.ylim(ymin=1e-10, ymax=1e4)
plt.xlim(xmin=1e-6, xmax=1.)
ax.set_xscale("log")
ax.set_yscale("log")
plt.savefig(path + '/Plots/' + Svname)
