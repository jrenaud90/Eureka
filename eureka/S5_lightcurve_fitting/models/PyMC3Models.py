import numpy as np
import matplotlib.pyplot as plt

import starry
import pymc3 as pm
import theano.tensor as tt
import exoplanet
import astropy.constants as const

from ...lib.readEPF import Parameters
from ..utils import COLORS

starry.config.quiet = True

class fit_class:
    def __init__(self):
        pass

BoundedNormal_0 = pm.Bound(pm.Normal, lower=0.0)
BoundedNormal_90 = pm.Bound(pm.Normal, upper=90.)

class StarryModel(pm.Model):
    def __init__(self, **kwargs):
        # Inherit from Model class
        super().__init__()

        # Define model type (physical, systematic, other)
        self.modeltype = 'physical'

        # Check for Parameters instance
        self.parameters = kwargs.get('parameters')
        # Set parameters for multi-channel fits
        self.longparamlist = kwargs.get('longparamlist')
        self.nchan = kwargs.get('nchan')
        self.paramtitles = kwargs.get('paramtitles')

        self.components = [self]

        required = np.array(['Ms', 'Mp', 'Rs'])
        missing = np.array([name not in self.paramtitles for name in required])
        if np.any(missing):
            raise AssertionError(f'Missing required params {required[missing]} in your EPF.')

        with self:
            for parname in self.paramtitles:
                param = getattr(self.parameters, parname)
                if param.ptype == 'independent':
                    continue
                elif param.ptype == 'fixed':
                    setattr(self, parname, tt.constant(param.value))
                else:
                    if param.ptype=='free':
                        if self.nchan==1:
                            shape = 1
                        else:
                            # FINDME: multi-wavelength fits do not currently work
                            shape = (1,self.nchan)
                    elif param.ptype=='shared':
                        shape = ()
                    else:
                        raise ValueError(f'ptype {param.ptype} for parameter {param.name} is not recognized.')
                    if param.prior == 'U':
                        setattr(self, parname, pm.Uniform(parname, lower=param.priorpar1, upper=param.priorpar2))#, shape=shape))
                    elif param.prior == 'N':
                        if parname in ['rp', 'per', 'ecc', 'scatter_mult', 'scatter_ppm', 'c0']:
                            setattr(self, parname, BoundedNormal_0(parname, mu=param.priorpar1, sigma=param.priorpar2))#, shape=shape))
                        elif parname in ['inc']:
                            setattr(self, parname, BoundedNormal_90(parname, mu=param.priorpar1, sigma=param.priorpar2))#, shape=shape))
                        else:
                            setattr(self, parname, pm.Normal(parname, mu=param.priorpar1, sigma=param.priorpar2))#, shape=shape))
                    elif param.prior == 'LU':
                        setattr(self, parname, tt.exp(pm.Uniform(parname, lower=param.priorpar1, upper=param.priorpar2)))#, shape=shape)))

            # Initialize star object
            if hasattr(self, 'u2'):
                udeg = 2
            elif hasattr(self, 'u1'):
                udeg = 1
            else:
                udeg = 0
            self.star = starry.Primary(starry.Map(ydeg=0, udeg=udeg, amp=1.0), m=self.Ms, r=self.Rs, prot=1.0)

            # FINDME: non-uniform limb darkening does not currently work
            if self.parameters.limb_dark.value == 'kipping2013':
                # Transform stellar variables to uniform used by starry
                self.u1_quadratic = pm.Deterministic('u1_quadratic', 2*tt.sqrt(self.u1)*self.u2)
                self.u2_quadratic = pm.Deterministic('u2_quadratic', tt.sqrt(self.u1)*(1-2*self.u2))
                self.star.map[1] = self.u1_quadratic
                self.star.map[2] = self.u2_quadratic
            elif self.parameters.limb_dark.value == 'quadratic':
                self.star.map[1] = self.u1
                self.star.map[2] = self.u2
            elif self.parameters.limb_dark.value == 'linear':
                self.star.map[1] = self.u1
            elif self.parameters.limb_dark.value != 'uniform':
                raise ValueError(f'ERROR: starryModel is not yet able to handle {self.parameters.limb_dark.value} limb darkening.\n'+
                                 f'       limb_dark must be one of uniform, linear, quadratic, or kipping2013.')

            # Initialize planet object
            if hasattr(self, 'AmpCos2') or hasattr(self, 'AmpSin2'):
                self.ydeg=2
            elif hasattr(self, 'AmpCos1') or hasattr(self, 'AmpSin1'):
                self.ydeg=1
            else:
                self.ydeg=0
            if hasattr(self, 'fp'):
                amp = self.fp
            else:
                amp = 0
            self.planet = starry.Secondary(
                starry.Map(ydeg=self.ydeg, udeg=0, amp=amp, inc=90.0, obl=0.0),
                m=self.Mp*const.M_jup.value/const.M_sun.value, # Convert mass to M_sun units
                r=self.rp*self.Rs, # Convert radius to R_star units
                a=self.a, # Setting porb here overwrites a
                # porb = self.per,
                # prot = self.per,
                #inc=tt.arccos(b/a)*180/np.pi # Another option to set inclination using impact parameter
                inc=self.inc,
                ecc=self.ecc,
                w=self.w
            )
            self.planet.porb = self.per # Setting porb here may not override a
            self.planet.prot = self.per # Setting prot here may not override a
            if hasattr(self, 'AmpCos1'):
                self.planet.map[1, 0] = self.AmpCos1
            if hasattr(self, 'AmpSin1'):
                self.planet.map[1, 1] = self.AmpSin1
            if self.ydeg==2:
                if hasattr(self, 'AmpCos2'):
                    self.planet.map[2, 0] = self.AmpCos2
                if hasattr(self, 'AmpSin2'):
                    self.planet.map[2, 1] = self.AmpSin2
            self.planet.theta0 = 180.0 # Offset is controlled by AmpSin1
            self.planet.tref = 0

            # Instantiate the system
            self.sys = starry.System(self.star, self.planet)

    @property
    def flux(self):
        """A getter for the flux"""
        return self._flux

    @flux.setter
    def flux(self, flux_array):
        """A setter for the flux

        Parameters
        ----------
        flux_array: sequence
            The flux array
        """
        # Check the type
        if not isinstance(flux_array, (np.ndarray, tuple, list)):
            raise TypeError("flux axis must be a tuple, list, or numpy array.")

        # Set the array
        self._flux = np.array(flux_array)
        # self._flux = np.ma.masked_array(flux_array)

    @property
    def parameters(self):
        """A getter for the parameters"""
        return self._parameters

    @parameters.setter
    def parameters(self, params):
        """A setter for the parameters"""
        # Process if it is a parameters file
        if isinstance(params, str) and os.path.isfile(params):
            params = Parameters(params)

        # Or a Parameters instance
        if (params is not None) and (type(params).__name__ != Parameters.__name__):
            raise TypeError("'params' argument must be a JSON file, ascii file, or Parameters instance.")

        # Set the parameters attribute
        self._parameters = params

    def setup(self, time, flux, lc_unc):
        self.time = time
        self.flux = flux
        self.lc_unc = lc_unc

        with self:
            if hasattr(self, 'scatter_mult'):
                # Fitting the noise level as a multiplier
                self.scatter_ppm = pm.Deterministic("scatter_ppm", self.scatter_mult*self.lc_unc)
            if not hasattr(self, 'scatter_ppm'):
                # Not fitting the noise level
                self.scatter_ppm = self.lc_unc

            # This is how we tell `pymc3` about our observations;
            # we are assuming they are ampally distributed about
            # the true model. This line effectively defines our
            # likelihood function.
            pm.Normal("obs", mu=self.eval(eval=False), sd=self.scatter_ppm, observed=self.flux)

        return

    def eval(self, eval=True, **kwargs):
        return self.physeval(eval=eval)[0]*self.syseval(eval=eval)

    def syseval(self, eval=True):
        if eval:
            # This is only called for things like plotting, so looping doesn't matter
            poly_coeffs = np.zeros((self.nchan,10))
            ramp_coeffs = np.zeros((self.nchan,6))
            # Add fitted parameters
            for k, v in self.fit_dict.items():
                if k.lower().startswith('c'):
                    k = k[1:]
                    remvisnum=k.split('_')
                    if k.isdigit():
                        poly_coeffs[0,int(k)] = v
                    elif len(remvisnum)>1 and self.nchan>1:
                        if remvisnum[0].isdigit() and remvisnum[1].isdigit():
                            poly_coeffs[int(remvisnum[1]),int(remvisnum[0])] = v
                elif k.lower().startswith('r'):
                    k = k[1:]
                    remvisnum=k[1:].split('_')
                    if k.isdigit():
                        ramp_coeffs[0,int(k)] = v
                    elif len(remvisnum)>1 and self.nchan>1:
                        if remvisnum[0].isdigit() and remvisnum[1].isdigit():
                            ramp_coeffs[int(remvisnum[1]),int(remvisnum[0])] = v

            poly_coeffs=poly_coeffs[:,~np.all(poly_coeffs==0,axis=0)]
            poly_coeffs=np.flip(poly_coeffs,axis=1)
            poly_flux = np.zeros(0)
            time_poly = self.time - self.time.mean()
            for c in range(self.nchan):
                poly = np.poly1d(poly_coeffs[c])
                poly_flux = np.append(poly_flux, np.polyval(poly, time_poly))

            ramp_flux = np.zeros(0)
            time_ramp = self.time - self.time[0]
            for c in range(self.nchan):
                r0, r1, r2, r3, r4, r5 = ramp_coeffs[c]
                lcpiece = r0*np.exp(-r1*time_ramp + r2) + r3*np.exp(-r4*time_ramp + r5) + 1
                ramp_flux = np.append(ramp_flux, lcpiece)

            return poly_flux*ramp_flux
        else:
            # This gets compiled before fitting, so looping doesn't matter
            poly_coeffs = np.zeros((self.nchan,10)).tolist()
            ramp_coeffs = np.zeros((self.nchan,6)).tolist()
            # Add fitted parameters
            for k in self.paramtitles:
                if k.lower().startswith('c'):
                    k = k[1:]
                    remvisnum=k.split('_')
                    if k.isdigit():
                        poly_coeffs[0][int(k)] = getattr(self, 'c'+k)
                    elif len(remvisnum)>1 and self.nchan>1:
                        if remvisnum[0].isdigit() and remvisnum[1].isdigit():
                            poly_coeffs[int(remvisnum[1])][int(remvisnum[0])] = getattr(self, 'c'+k)
                elif k.lower().startswith('r'):
                    k = k[1:]
                    remvisnum=k[1:].split('_')
                    if k.isdigit():
                        ramp_coeffs[0][int(k)] = getattr(self, 'r'+k)
                    elif len(remvisnum)>1 and self.nchan>1:
                        if remvisnum[0].isdigit() and remvisnum[1].isdigit():
                            ramp_coeffs[int(remvisnum[1])][int(remvisnum[0])] = getattr(self, 'r'+k)

            poly_flux = tt.zeros(0)
            time_poly = self.time - self.time.mean()
            for c in range(self.nchan):
                lcpiece = tt.zeros(len(self.time))
                for power in range(len(poly_coeffs[c])):
                    lcpiece += poly_coeffs[c][power] * time_poly**power
                poly_flux = tt.concatenate([poly_flux, lcpiece])

            ramp_flux = tt.zeros(0)
            time_ramp = self.time - self.time[0]
            for c in range(self.nchan):
                r0, r1, r2, r3, r4, r5 = ramp_coeffs[c]
                lcpiece = r0*tt.exp(-r1*time_ramp + r2) + r3*tt.exp(-r4*time_ramp + r5) + 1
                ramp_flux = tt.concatenate([ramp_flux, lcpiece])

            return poly_flux*ramp_flux

    def physeval(self, interp=False, eval=True):
        if interp:
            dt = self.time[1]-self.time[0]
            steps = int(np.round((self.time[-1]-self.time[0])/dt+1))
            new_time = np.linspace(self.time[0], self.time[-1], steps, endpoint=True)
        else:
            new_time = self.time

        if eval:
            return self.fit.sys.flux(new_time-self.fit.t0).eval(), new_time
        else:
            return self.sys.flux(new_time-self.t0), new_time

    @property
    def fit_dict(self):
        return self._fit_dict

    @fit_dict.setter
    def fit_dict(self, input_fit_dict):
        self._fit_dict = input_fit_dict

        fit = fit_class()
        for key in self.fit_dict.keys():
            setattr(fit, key, self.fit_dict[key])

        for parname in self.paramtitles:
            param = getattr(self.parameters, parname)
            if param.ptype == 'independent':
                continue
            elif param.ptype == 'fixed':
                setattr(fit, parname, param.value)

        # Initialize star object
        if hasattr(fit, 'u2'):
            udeg = 2
        elif hasattr(fit, 'u1'):
            udeg = 1
        else:
            udeg = 0
        fit.star = starry.Primary(starry.Map(ydeg=0, udeg=udeg, amp=1.0), m=fit.Ms, r=fit.Rs, prot=1.0)

        if self.parameters.limb_dark.value == 'kipping2013':
            # Transform stellar variables to uniform used by starry
            fit.u1_quadratic = pm.Deterministic('u1_quadratic', 2*tt.sqrt(fit.u1)*fit.u2)
            fit.u2_quadratic = pm.Deterministic('u2_quadratic', tt.sqrt(fit.u1)*(1-2*fit.u2))
            fit.star.map[1] = fit.u1_quadratic
            fit.star.map[2] = fit.u2_quadratic
        elif self.parameters.limb_dark.value == 'linear':
            fit.star.map[1] = fit.u1
        elif self.parameters.limb_dark.value == 'quadratic':
            fit.star.map[1] = fit.u1
            fit.star.map[2] = fit.u2
        elif self.parameters.limb_dark.value != 'uniform':
            raise ValueError(f'ERROR: starryModel is not yet able to handle {self.parameters.limb_dark.value} limb darkening.\n'+
                            f'       limb_dark must be one of uniform, linear, quadratic, or kipping2013.')

        # Initialize planet object
        if hasattr(fit, 'AmpCos2') or hasattr(fit, 'AmpSin2'):
            fit.ydeg=2
        elif hasattr(fit, 'AmpCos1') or hasattr(fit, 'AmpSin1'):
            fit.ydeg=1
        else:
            fit.ydeg=0
        # if hasattr(fit, 'fp'):
        #     amp = fit.fp
        # else:
        #     amp = 0
        fit.planet = starry.Secondary(
            starry.Map(ydeg=fit.ydeg, udeg=0, amp=fit.fp, inc=90.0, obl=0.0),
            m=fit.Mp*const.M_jup.value/const.M_sun.value,
            r=fit.rp*fit.Rs,
            # a=fit.a, # Setting porb overwrites a
            porb = fit.per,
            prot = fit.per,
            #inc=tt.arccos(b/a)*180/np.pi
            inc=fit.inc,
            ecc=fit.ecc,
            w=fit.w
        )
        # fit.planet.porb = fit.per
        # fit.planet.prot = fit.per
        if hasattr(fit, 'AmpCos1'):
            fit.planet.map[1, 0] = fit.AmpCos1
        if hasattr(fit, 'AmpSin1'):
            fit.planet.map[1, 1] = fit.AmpSin1
        if fit.ydeg==2:
            if hasattr(fit, 'AmpCos2'):
                fit.planet.map[2, 0] = fit.AmpCos2
            if hasattr(fit, 'AmpSin2'):
                fit.planet.map[2, 1] = fit.AmpSin2
        fit.planet.theta0 = 180.0 # Offset is controlled by AmpSin1
        fit.planet.tref = 0

        # Instantiate the system
        fit.sys = starry.System(fit.star, fit.planet)

        self.fit = fit

        return

    def plot(self, time, components=False, ax=None, draw=False, color='blue', zorder=np.inf, share=False, chan=0, **kwargs):
        """Plot the model

        Parameters
        ----------
        time: array-like
            The time axis to use
        components: bool
            Plot all model components
        ax: Matplotlib Axes
            The figure axes to plot on

        Returns
        -------
        bokeh.plotting.figure
            The figure
        """
        # Make the figure
        if ax is None:
            fig = plt.figure(figsize=(8,6))
            ax = fig.gca()

        # Set the time
        self.time = time

        # Plot the model
        label = self.fitter
        if self.name!='New Model':
            label += ': '+self.name
        
        flux = self.eval(**kwargs)
        if share:
            flux = flux[chan*len(self.time):(chan+1)*len(self.time)]
        
        ax.plot(self.time, flux, '.', ls='', ms=2, label=label, color=color, zorder=zorder)

        if components and self.components is not None:
            for comp in self.components:
                comp.plot(self.time, ax=ax, draw=False, color=next(COLORS), zorder=zorder, share=share, chan=chan, **kwargs)

        # Format axes
        ax.set_xlabel(str(self.time_units))
        ax.set_ylabel('Flux')

        if draw:
            fig.show()
        else:
            return

    @property
    def time(self):
        """A getter for the time"""
        return self._time

    @time.setter
    def time(self, time_array, time_units='BJD'):
        """A setter for the time

        Parameters
        ----------
        time_array: sequence, astropy.units.quantity.Quantity
            The time array
        time_units: str
            The units of the input time_array, ['MJD', 'BJD', 'phase']
        """
        # Check the type
        if not isinstance(time_array, (np.ndarray, tuple, list)):
            raise TypeError("Time axis must be a tuple, list, or numpy array.")

        # Set the units
        self.time_units = time_units

        # Set the array
        self._time = time_array
