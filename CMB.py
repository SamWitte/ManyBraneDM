import numpy as np
import os
from boltzmann import *
from frw_metric import *
from scipy.integrate import quad
from scipy.interpolate import interp1d
from scipy.special import spherical_jn
from scipy.optimize import minimize
from statsmodels.nonparametric.smoothers_lowess import lowess
#from scipy.signal import savgol_filter
from multiprocessing import Pool
import glob
import math
path = os.getcwd()

class CMB(object):

    def __init__(self, OM_b, OM_c, OM_g, OM_L, kmin=5e-3, kmax=0.5, knum=200,
                 lmax=2500, lvals=250,
                 Ftag='StandardUniverse', lmax_Pert=5, multiverse=False,
                 OM_b2=0., OM_c2=0., OM_g2=0., OM_L2=0., Nbrane=0):
        
        self.OM_b = OM_b
        self.OM_c = OM_c
        self.OM_g = OM_g
        self.OM_L = OM_L
        self.OM_nu = (7./8)*(4./11.)**(4./3)*3.04 * OM_g

        self.OM_b2 = OM_b2
        self.OM_c2 = OM_c2
        self.OM_g2 = OM_g2
        self.OM_L2 = OM_L2
        self.OM_nu2 = (7./8)*(4./11.)**(4./3)*3.04 * OM_g2
        self.Nbrane = Nbrane
        if OM_b2 != 0.:
            self.PressFac = (OM_g2 / OM_b2) / (OM_g / OM_b)
        else:
            self.PressFac = 0.
        
        self.eCDM = OM_c + OM_c2 * Nbrane
        
        self.kmin = kmin
        self.kmax = kmax
        self.knum = knum
        self.Ftag = Ftag
        if multiverse:
            self.f_tag = '_Nbranes_{:.0e}_PressFac_{:.2e}_eCDM_{:.2e}'.format(self.Nbrane, self.PressFac, self.eCDM)
        else:
            self.f_tag = ''
        
        self.lmax = lmax
        self.lvals = lvals
        self.H_0 = 2.2348e-4 # units Mpc^-1
        self.lmax_Pert = lmax_Pert
        self.lmin = 10
        
        self.multiverse = multiverse
        self.init_pert = -1/6.
        
#        ell_val = range(self.lmin, self.lmax, 10)
        ell_val = np.logspace(np.log10(self.lmin), np.log10(self.lmax), 120)
        self.clearfiles()
        
        self.ThetaFile = path + '/OutputFiles/' + self.Ftag
        if self.multiverse:
            self.ThetaFile += '_Nbrane_{:.0e}_PressFac_{:.2e}_eCDM_{:.2e}_ThetaCMB_Table.dat'.format(self.Nbrane, self.PressFac, self.eCDM)
        else:
            self.ThetaFile += '_ThetaCMB_Table.dat'

        self.ThetaTabTot = np.zeros((self.knum+1, len(ell_val)))
        self.ThetaTabTot[0,:] = ell_val

        self.fill_inx = 0
        self.loadfiles()
    
    def runall(self, kVAL=None, compute_LP=False, compute_TH=False,
               compute_CMB=False, compute_MPS=False):
        
        if compute_MPS:
            self.kgrid = np.logspace(np.log10(self.kmin), np.log10(self.kmax), self.knum)
        else:
            #self.kgrid = np.linspace(self.kmin, self.kmax, self.knum)
            self.kgrid = np.logspace(np.log10(self.kmin), np.log10(self.kmax), self.knum)
        
        if compute_LP:
            print 'Computing Perturbation Fields...\n'
            self.kspace_linear_pert(kVAL)
        
        if compute_TH:
            print 'Computing Theta Files...\n'
            
            if kVAL is not None:
                self.theta_integration(kVAL, kVAL=kVAL)
            else:
                for k in self.kgrid:
                    self.theta_integration(k)
                    
        if compute_CMB:
            print 'Computing CMB...\n'
            self.computeCMB()
        if compute_MPS:
            print 'Computing Matter Power Spectrum...\n'
            self.MatterPower()
        return
    
    def clearfiles(self):
        if os.path.isfile(path + '/precomputed/xe_working' + self.f_tag + '.dat'):
            os.remove(path + '/precomputed/xe_working' + self.f_tag + '.dat')
        if os.path.isfile(path + '/precomputed/tb_working' + self.f_tag + '.dat'):
            os.remove(path + '/precomputed/tb_working' + self.f_tag + '.dat')

        if os.path.isfile(path + '/precomputed/working_expOpticalDepth' + self.f_tag + '.dat'):
            os.remove(path + '/precomputed/working_expOpticalDepth' + self.f_tag + '.dat')
        if os.path.isfile(path + '/precomputed/working_VisibilityFunc' + self.f_tag + '.dat'):
            os.remove(path + '/precomputed/working_VisibilityFunc' + self.f_tag + '.dat')
    
    def loadfiles(self):
    
        if not self.multiverse:
            SingleUni = Universe(1., self.OM_b, self.OM_c, self.OM_g, self.OM_L, self.OM_nu)
            self.ct_to_scale = lambda x: SingleUni.ct_to_scale(x)
            self.scale_to_ct = lambda x: SingleUni.scale_to_ct(x)
            SingleUni.tau_functions()
            self.eta0 = SingleUni.eta_0
        else:
            ManyUni = ManyBrane_Universe(self.Nbrane, 1., [self.OM_b, self.OM_b2], [self.OM_c, self.OM_c2],
                                          [self.OM_g, self.OM_g2], [self.OM_L, self.OM_L2],
                                          [self.OM_nu, self.OM_nu2])
            self.ct_to_scale = lambda x: ManyUni.ct_to_scale(x)
            self.scale_to_ct = lambda x: ManyUni.scale_to_ct(x)
            ManyUni.tau_functions()
            self.eta0 = ManyUni.eta_0
    
        opt_depthL = np.loadtxt(path + '/precomputed/working_expOpticalDepth' + self.f_tag + '.dat')
        self.opt_depth = interp1d(np.log10(opt_depthL[:,0]), opt_depthL[:,1], kind='cubic',
                                  bounds_error=False, fill_value='extrapolate')

        visfunc = np.loadtxt(path + '/precomputed/working_VisibilityFunc' + self.f_tag + '.dat')
        self.Vfunc = interp1d(np.log10(visfunc[:,0]), visfunc[:,1], kind='cubic', bounds_error=False, fill_value=0.)
        self.eta_start = 10.**self.scale_to_ct(np.log10(np.min(visfunc[:,0])))
        
        return

    def kspace_linear_pert(self, kVAL=None):
        #kgrid = np.logspace(np.log10(self.kmin), np.log10(self.kmax), self.knum)
        if kVAL is not None:
            kgrid = [kVAL]
        else:
            kgrid = self.kgrid
        for k in kgrid:
            if self.multiverse:
                fileName = path + '/OutputFiles/' + self.Ftag + \
                         '_FieldEvolution_{:.4e}_Nbrane_{:.0e}_PressFac_{:.2e}_eCDM_{:.2e}.dat'.format(k, self.Nbrane,
                                                                                                       self.PressFac, self.eCDM)
            else:
                fileName = path + '/OutputFiles/' + self.Ftag + '_FieldEvolution_{:.4e}.dat'.format(k)
            if os.path.isfile(fileName):
                continue
            stepsize = 1e-2
            success = False
            while not success:
                print 'Working on k = {:.3e}, step size = {:.3e}'.format(k, stepsize)
                try:
                    if not self.multiverse:
                        SingleUni = Universe(k, self.OM_b, self.OM_c, self.OM_g, self.OM_L, self.OM_nu,
                                             stepsize=stepsize, accuracy=1e-3, lmax=self.lmax_Pert).solve_system()
                    else:
                        ManyBrane_Universe(self.Nbrane, k, [self.OM_b, self.OM_b2], [self.OM_c, self.OM_c2],
                                          [self.OM_g, self.OM_g2], [self.OM_L, self.OM_L2],
                                          [self.OM_nu, self.OM_nu2], accuracy=1e-3,
                                          stepsize=stepsize, lmax=self.lmax_Pert).solve_system()
                    success = True
                except ValueError:
                    stepsize /= 2.
    
        print 'All k values computed!'
        return


    def theta_integration(self, k, kVAL=None):
        filename = path + '/OutputFiles/' + self.Ftag + '_ThetaFile_kval_{:.4e}'.format(k)
        if self.multiverse:
            filename += '_Nbrane_{:.0e}_PressFac_{:.2e}_eCDM_{:.2e}.dat'.format(self.Nbrane, self.PressFac, self.eCDM)
        else:
            filename += '.dat'
        
        if os.path.isfile(filename):
            return
        if kVAL is not None:
            #kgrid = np.logspace(np.log10(self.kmin), np.log10(self.kmax), self.knum)
            index = np.where(self.kgrid == kVAL)[0][0] + 1
        ell_tab = self.ThetaTabTot[0,:]
        
        fileNme = path + '/OutputFiles/' + self.Ftag + '_FieldEvolution_{:.4e}'.format(k)
        if self.multiverse:
            fileNme += '_Nbrane_{:.0e}_PressFac_{:.2e}_eCDM_{:.2e}.dat'.format(self.Nbrane, self.PressFac, self.eCDM)
        else:
            fileNme += '.dat'
        fields = np.loadtxt(fileNme)

        thetaVals = np.zeros(len(ell_tab))
        indx_min = np.argmin(np.abs(fields[:, 0] - 50.))
        vis = self.visibility(fields[indx_min:, 0])
        
        deta0 = np.diff(fields[:,0])
        h1 = deta0[indx_min+1:]
        h2 = deta0[indx_min:-1]
        pre_2nd_derTerm = (fields[:, 7] + fields[:, 12] + fields[:, 13])*self.visibility(fields[:, 0])
        
        sec_DerTerm = 2.*(h2*pre_2nd_derTerm[indx_min+2:] - (h1+h2)*pre_2nd_derTerm[indx_min+1:-1] + h1*pre_2nd_derTerm[indx_min:-2])/(h1*h2*(h1+h2))
        sec_DerTerm = np.insert(sec_DerTerm, 0, 0.)
        sec_DerTerm = np.insert(sec_DerTerm, 0, 0.)
        
        tpsi0 = fields[indx_min:, 6] + fields[indx_min:, -1]
        pipolar = fields[indx_min:, 7] + fields[indx_min:, 12] + fields[indx_min:, 13]
        vb0 = fields[indx_min:, 5]
        expD0 = self.exp_opt_depth(fields[indx_min:, 0])
        
        ppdot0 = (np.diff(fields[indx_min:, 1]) - np.diff(fields[indx_min:, -1])) / np.diff(fields[indx_min:, 0])
        ppdot0 = np.insert(ppdot0, 0, 0.)
        
        s_filter = 0.008
        smthed_ppdot0 = lowess(fields[indx_min:, 0], ppdot0, frac=s_filter, return_sorted=True)
        
        for i,ell in enumerate(ell_tab):
            integ1 = vis * (tpsi0 + pipolar/4. + 3./4./k**2.*sec_DerTerm) * spherical_jn(int(ell), k * (self.eta0 - fields[indx_min:, 0]))
            integ2 = vis * vb0 * (spherical_jn(int(ell - 1.), k * (self.eta0 - fields[indx_min:, 0])) - \
                    (ell+1.)*spherical_jn(int(ell), k * (self.eta0 - fields[indx_min:, 0]))/(k * (self.eta0 - fields[indx_min:, 0])))
            integ3 = -expD0 * smthed_ppdot0[:,0] * spherical_jn(int(ell), k * (self.eta0 - fields[indx_min:, 0]))
            integ1[np.isnan(integ1)] = 0.
            integ2[np.isnan(integ2)] = 0.
            integ3[np.isnan(integ3)] = 0.

            term1 = np.trapz(integ1, fields[indx_min:, 0])
            term2 = np.trapz(integ2, fields[indx_min:, 0])
            term3 = np.trapz(integ3, fields[indx_min:, 0])
            thetaVals[i] = term1 + term2 + term3
    
        np.savetxt(filename, thetaVals)
        return
        

    def SaveThetaFile(self, test=False):
        
        kgrid = np.logspace(np.log10(self.kmin), np.log10(self.kmax), self.knum)
        if os.path.isfile(self.ThetaFile):
            os.remove(self.ThetaFile)
        
        t_file_nmes = path + '/OutputFiles/' + self.Ftag + '_ThetaFile_kval_*'
        if self.multiverse:
            extraTG = '_Nbrane_{:.0e}_PressFac_{:.2e}_eCDM_{:.2e}.dat'.format(self.Nbrane, self.PressFac, self.eCDM)
        else:
            extraTG = '.dat'
        t_file_nmes += extraTG
        
        ThetaFiles = glob.glob(t_file_nmes)
        klist = np.array([])
        for i in range(len(ThetaFiles)):
            if not self.multiverse:
                kval = float(ThetaFiles[i][ThetaFiles[i].find('kval_')+5:ThetaFiles[i].find('.dat')])
            else:
                kval = float(ThetaFiles[i][ThetaFiles[i].find('kval_')+5:ThetaFiles[i].find('_Nbrane_')])
            klist = np.append(klist, kval)
        
        klist = np.sort(klist)
        for i in range(len(ThetaFiles)):
            dat = np.loadtxt(path + '/OutputFiles/' + self.Ftag + '_ThetaFile_kval_{:.4e}'.format(klist[i]) + extraTG)
            self.ThetaTabTot[i+1,:] = dat
            os.remove(path + '/OutputFiles/' + self.Ftag + '_ThetaFile_kval_{:.4e}'.format(klist[i]) + extraTG)
        np.savetxt(self.ThetaFile, self.ThetaTabTot, fmt='%.4e')
        
        if test:
            np.savetxt(path + '/OutputFiles/TESTING_THETA.dat', np.column_stack((kgrid, self.ThetaTabTot[1:,:])))
        return

    def computeCMB(self):
        thetaTab = np.loadtxt(self.ThetaFile)
        ell_tab = self.ThetaTabTot[0,:]
        CL_table = np.zeros((len(ell_tab), 2))
        if not self.multiverse:
            GF = ((self.OM_b+self.OM_c) / self.growthFactor(1.))**2.
        else:
            GF = ((self.OM_b+self.OM_c + (self.OM_b2 + self.OM_c2)*self.Nbrane) / self.growthFactor(1.))**2.
        
        for i,ell in enumerate(ell_tab):
            cL_interp = interp1d(self.kgrid, (thetaTab[1:, i]/self.init_pert), kind='cubic', fill_value=0.)
            CLint = quad(lambda x: (x/self.H_0)**(0.96605-1.)*100.*np.pi/(9.)*cL_interp(x)**2./x, self.kgrid[0], self.kgrid[-1], limit=300)
            CL_table[i] = [ell, ell*(ell+1)/(2.*np.pi)*CLint[0]*GF]
            if math.isnan(CLint[0]):
                print i, ell
                print np.abs(thetaTab[1:, i]/self.init_pert)**2.
                print thetaTab[1:, i]
                print cL_interp(np.log10(self.kgrid))
                exit()

        Cl_name = path + '/OutputFiles/' + self.Ftag + '_CL_Table'
        if self.multiverse:
            Cl_name += '_Nbrane_{:.0e}_PressFac_{:.2e}_eCDM_{:.2e}.dat'.format(self.Nbrane, self.PressFac, self.eCDM)
        else:
            Cl_name += '.dat'
        np.savetxt(Cl_name, CL_table)
        return

    def growthFactor(self, a):
        # D(a)
        if not self.multiverse:
            Uni = Single_FRW(self.OM_b, self.OM_c, self.OM_L, self.OM_g, self.H_0)
            prefac = 5.*(self.OM_b + self.OM_c)/2. *(Uni.Hubble(a) / self.H_0) * self.H_0**3.
        else:
            omB = self.OM_b + self.OM_b2 * self.Nbrane
            omC = self.OM_c + self.OM_c2 * self.Nbrane
            Uni = Single_FRW(omB, omC, self.OM_L, self.OM_g + self.OM_g2 * self.Nbrane, self.H_0)
            
            prefac = 5.*(omB + omC)/2. *(Uni.Hubble(a) / self.H_0) * self.H_0**3.
    
        integ_pt = quad(lambda x: 1./(x*Uni.Hubble(x)**3.), 0., a)[0]
        return prefac * integ_pt

    def exp_opt_depth(self, eta):
        aval = 10.**self.ct_to_scale(np.log10(eta))
        return self.opt_depth(np.log10(aval))
    
    def visibility(self, eta):
        ln10aval = self.ct_to_scale(np.log10(eta))
        return self.Vfunc(ln10aval)
    
    def vis_max_eta(self):
        etaL = np.logspace(0, np.log10(self.eta0), 10000)
        visEval = self.visibility(etaL)
        return etaL[np.argmax(visEval)]

    def MatterPower(self):
        # T(k) = \Phi(k, a=1) / \Phi(k = Large, a= 1)
        # P(k,a=1) = 2 pi^2 * \delta_H^2 * k / H_0^4 * T(k)^2
        Tktab = self.TransferFuncs()
        #kgrid = np.logspace(np.log10(self.kmin), np.log10(self.kmax), self.knum)
        PS = np.zeros_like(self.kgrid)
        for i,k in enumerate(self.kgrid):
            PS[i] = k*Tktab[i]**2.
        if self.multiverse:
            np.savetxt(path + '/OutputFiles/' + self.Ftag +
                       '_MatterPowerSpectrum_Nbrane_{:.0e}_PressFac_{:.2e}_eCDM_{:.2e}.dat'.format(self.Nbrane,self.PressFac,self.eCDM),
                       np.column_stack((self.kgrid, PS)))
        else:
            np.savetxt(path + '/OutputFiles/' + self.Ftag + '_MatterPowerSpectrum.dat', np.column_stack((self.kgrid, PS)))
        return

    def TransferFuncs(self):
        if self.multiverse:
            Minfields = np.loadtxt(path + '/OutputFiles/' + self.Ftag +
                        '_FieldEvolution_{:.4e}_Nbrane_{:.0e}_PressFac_{:.2e}_eCDM_{:.2e}.dat'.format(self.kmin, self.Nbrane,
                        self.PressFac, self.eCDM))
        else:
            Minfields = np.loadtxt(path + '/OutputFiles/' + self.Ftag + '_FieldEvolution_{:.4e}.dat'.format(self.kmin))
        LargeScaleVal = Minfields[-1, 1]
        #kgrid = np.logspace(np.log10(self.kmin), np.log10(self.kmax), self.knum)
        Tktab = np.zeros_like(self.kgrid)
        for i,k in enumerate(self.kgrid):
            if self.multiverse:
                field =  np.loadtxt(path + '/OutputFiles/'+ self.Ftag +
                                    '_FieldEvolution_{:.4e}_Nbrane_{:.0e}_PressFac_{:.2e}_eCDM_{:.2e}.dat'.format(k, self.Nbrane,
                                    self.PressFac, self.eCDM))
            else:
                field =  np.loadtxt(path + '/OutputFiles/' + self.Ftag + '_FieldEvolution_{:.4e}.dat'.format(k))
            Tktab[i] = field[-1,1] / LargeScaleVal
        return Tktab


