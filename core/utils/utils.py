import pandas as pd
import numpy as np

from data_loading import load_gravitational_wave_data, load_neutrino_data
from utils.far import match_far, cut_off
from pydantic import BaseModel, Field

GW_BG_FARS = np.loadtxt("/home/aki/snakepit/multi_messenger_astro/data/gw_data/false_alarm_list.csv", delimiter=",")  


def save_dict_to_hdf5(data_dict, filepath):
    """
    Save a dictionary of Pandas DataFrames to an HDF5 file.
    
    Args:
        data_dict (dict): Dictionary where keys are dataset names and values are DataFrames.
        filepath (str): Path to the output HDF5 file.
    """
    with pd.HDFStore(filepath, mode="w") as store:
        for key, df in data_dict.items():
            store.put(key, df)  # Save each DataFrame under its key
    print(f"Saved {len(data_dict)} DataFrames to {filepath}")


def load_hdf5_to_dict(filepath):
    """
    Load an HDF5 file into a dictionary of Pandas DataFrames.
    
    Args:
        filepath (str): Path to the HDF5 file.
    
    Returns:
        dict: Dictionary where keys are dataset names and values are DataFrames.
    """
    data_dict = {}
    with pd.HDFStore(filepath, mode="r") as store:
        for key in store.keys():
            data_dict[key.strip("/")] = store[key]  # Remove leading '/'
    return data_dict


def Poisson(k, lamb):
    """Poisson probability density function with lamb mean 
    and k observed events."""
    k = int(k)
    return lamb**k * np.exp(-lamb) / np.math.factorial(k)

gw_data = load_gravitational_wave_data()
gpstime_source = gw_data["gpstime"]
mass1_source = gw_data["mass1"]
mass2_source = gw_data["mass2"]
distance_source = gw_data["distance"]
inc_source = gw_data["inclination"]
ra_source = gw_data["right_ascension"]
dec_source = gw_data["declination"]
far_gstlal = gw_data["far_gstlal"]
far_mbta = gw_data["far_mbta"]
far_pycbc_hyperbank = gw_data["far_pycbc_hyperbank"]
far_pycbc_bbh = gw_data["far_pycbc_bbh"]
alt_source = gw_data["altitude"]
az_source = gw_data["azimuth"]

nu_data = load_neutrino_data()


def temporal(T_obs):
    return T_obs**-1


def Pr(r, search_parameters):
    r_max = max(distance_source)
    N_r = r_max**3 / 3  # normalizing the distance distribution
    return r**2 / N_r


def sky_dist():
    """Probability distribution of angular sky position of events. It is assumed be uniformly distributed across sky."""
    return (4*np.pi)**-1


def PMgw(mass1, mass2, search_params):
    """Probability of the source mass distribution of objects of merger that produced the gravitational wave."""
    m1_max, m1_min = search_params.Mgwmax, search_params.Mgwmin
    m2_max, m2_min = search_params.Mgwmax, search_params.Mgwmin
 
    normalization_mass1, normalization_mass2 = (
        np.log(m1_max / m1_min),
        np.log(m2_max / m2_min),
    )  # normalization of the mass distributions
    return mass1**-1 * mass2**-1 * normalization_mass1**-1 * normalization_mass2**-1
 

def PEnu(Enu, search_params):
    """Probability of isotropic equivalent neutrino emission energy Enu given in the signal hypothesis."""
    normalization_total_E = np.log(search_params.Enumax/search_params.Enumin)
    return Enu**-1 * normalization_total_E**-1


def gravitational_conditional(gpstime, distance, ra, dec, M_1, M_2):
    """Retuns the source probability distribution for the gravitational wave source."""
    far = match_far(gpstime, distance, ra, dec, M_1, M_2)
    T_obs = 500
    return temporal(T_obs)*distance(distance)*sky_dist(ra, dec)*PMgw(M_1, M_2)*cut_off(far)


def Pfar(far):
    """Returns the probability of getting any given false alarm rate using
    the O3 Sensitivity Measurements dataset for the binwidths. Only including
    the false alarm rates below 2 per day since we only get measurements of them.
    
    Parameters
    ----------
    far: False alarm rate (Hz)"""
    far_gstlal_filtered = far_gstlal[far_gstlal <= 2]
    far_mbta_filtered = far_mbta[far_mbta <= 2]
    far_pycbc_hyperbank_filtered = far_pycbc_hyperbank[far_pycbc_hyperbank <= 2]
    far_total = np.concatenate(
        (far_gstlal_filtered, far_mbta_filtered, far_pycbc_hyperbank_filtered)
    )*86400  # All false alarm rates that are less than 2 per day
    bins = np.logspace(-52, np.log10(2.3e-5), num=(52-5)+1)

    counts, bin_edges = np.histogram(far_total, bins=bins, density=True)

    bin_widths = np.diff(bin_edges)
    probabilities = counts * bin_widths

    if far < bin_edges[0] or far > bin_edges[-1]: # False alarm rate is out of range
        return 0
    
    bin_i = np.digitize(far, bin_edges) - 1

    return probabilities[bin_i] if 0 <= bin_i < len(probabilities) else 0 


def Aeff(epsilon_nu, declination, dataframes_effectiveArea):
    """Returns the corresponding effective area of the neurino detection with 
    respect to the individual energy of detected neturino in log10 scale and 
     declination angle. """
    df = dataframes_effectiveArea["IC86_II_effectiveArea"]
    condition = (
        (df["log10(E_nu/GeV)_min"] <= epsilon_nu)
        & (epsilon_nu < df["log10(E_nu/GeV)_max"])
        & (df["Dec_nu_min[deg]"] <= declination)
        & (declination < df["Dec_nu_max[deg]"])
    )
    effective_area = df[condition]
    return effective_area.iloc[0]["A_Eff[cm^2]"]


def expnu(r, Enu,  search_params):
    """Count of expected neutrinos."""
    return search_params.nu_51_100*(Enu/search_params.Enumax)*(100/r)**2


def Pempfar(far):
    """Probability of a false alarm rate in null hypothesis, obtained from the
    histogram of all superevents released in GraceDB from O1 to end of O4. Empirical
    probability of a false alarm rate.
    
    Parameters
    ----------
    far: False alarm rate (Hz)"""
    far_data = GW_BG_FARS
    log_bins_1 = np.logspace(-52, -10, num=(52-10)+1)

    log_bins_2 = np.logspace(-10, np.log10(2.3e-5), num=4 * (int(np.log10(2.3e-5)) + 10))

    bins = np.concatenate([log_bins_1, log_bins_2])

    counts, bin_edges = np.histogram(far_data, bins=bins, density=True)

    bin_widths = np.diff(bin_edges)
    probabilities = counts * bin_widths

    if far < bin_edges[0] or far > bin_edges[-1]: # False alarm rate is out of range
        return 0
    
    bin_i = np.digitize(far, bin_edges) - 1

    return probabilities[bin_i] if 0 <= bin_i < len(probabilities) else 0


class IceCubeLIGO(BaseModel):
    """Collection of the search parameters."""
    nu_51_100: float = Field(..., description="Detector specific number for IceCube's neutrino detections.")
    tgwplus: float = Field(..., description="Upper limit for the GW detection time boundaries, in seconds.")
    tgwminus: float = Field(..., description="Lower limit for the GW detection time boundaries, in seconds.")
    tnuplus: float = Field(..., description="Upper limit for the neutrino detection time boundaries, in seconds.")
    tnuminus: float = Field(..., description="Lower limit for the neutrino detection time boundaries, in seconds.")
    fb: float = Field(..., description="Beaming factor for neutrinos.")
    ratebggw: float = Field(..., description="Background rates for the gravitational wave channels. Including every pipeline, in Hz.")
    ratebgnu: float = Field(..., description="Background neutrino detection rate in IceCube channels, obtained from IceCube data releases, in Hz.")
    ndotgw: float = Field(..., description="Observable gravitational wave rate, calculated in the integral in eq. (26)")
    ndotnu: float = Field(..., description="Observable astrophysical neutrino rate, calculated in the integral in eq. (29)")
    ndotgwnu: float = Field(..., description="Observable GW and neutrino multi-messenger rate.")
    Mgwmax: float = Field(..., description="""Maximum mass of one of the objects in a GW emitting event accounted by the model. Different
                          for the types of merger events released by LIGO's GraceDB. [kg]""")
    Mgwmin: float = Field(..., description="""Minimum mass of one of the objects in a GW emitting event accounted by the model. Different
                          for the types of merger events released by LIGO's GraceDB. [kg]""")
    Enumax: float = Field(..., description="Maximum isotropic-equivalent neutrino energy accounted by the model. [Ergs]")
    Enumin: float = Field(..., description="Minimum isotropic-equivalent neutrino energy accounted by the model. [Ergs]")
    epsilonmax: float = Field(..., description="Maximum neutrino energy for the integral upper bounds. [GeV]")
    epsilonmin: float = Field(..., description="Minimum detectible neutrino energy. [GeV]")
    farthr: float = Field(..., description="""False alarm rate threshold for gravitational wave detections. Events with false alarm
                          rate below this number are not detected by any pipelines. [Hz]""")
    population: str = Field(..., description="Name of the source population of gravitational wave events. Can be 'bns', 'bbh', 'nsbh'.")
    

def search_parameters(population):
    """Return an IceCubeLIGO instance with values ascribed into.
    population: "bbh", "bns", or "nsbh"
    """
    return IceCubeLIGO(
        nu_51_100 = 1.1,
        tgwplus = 250, # s
        tgwminus = -250, # s
        tnuplus = 250, # s
        tnuminus = -250, # s
        fb = 10.0, 
        ratebggw = 3.0*2.3*10**-5, # 1/s, 2 per day per pipeline (gstlal, mbta)
        ratebgnu = 0.0035055081034729364, # Background neurino rate, per second (1/s)
        ndotgw = 3.9255868248144146, # per year
        ndotnu = 2.7402641832764836e-05, # per year
        ndotgwnu = 1, #FIXME
        Mgwmax = 2.5*1.988*10**30, # 2.5 Solar Masses in Kgs for bns
        Mgwmin = 1.0*1.988*10**30, # 1.0 Solar Masses in Kgs for bns
        Enumax = 10**51, # erg
        Enumin = 10**46, # erg
        epsilonmax = 10**8, # GeV
        epsilonmin = 10.0**2, # GeV
        farthr = 2.3*10**-5, # Hz
        population=population
    )
    
def match_far(gpstime, distance, right_ascension, declination, mass1, mass2):
    """Finds a false alarm rate from the O3 Sensitivity measurements data set for the given parameters"""
    import astropy.units as u
    from astropy.coordinates import SkyCoord, EarthLocation, AltAz
    from astropy.time import Time

    location = EarthLocation(lon=0 * u.deg, lat=0 * u.deg, height=0 * u.m)

    t = Time(gpstime * u.s, format="gps")
    altaz = AltAz(obstime=t, location=location)
    observation = SkyCoord(
        ra=right_ascension * u.deg, dec=declination * u.deg, frame="icrs"
    )
    observation_alt_az = observation.transform_to(altaz)
    alt = observation_alt_az.alt.value
    az = observation_alt_az.az.value

    cos_angular_distance = np.sin(gw_data["altitude"]) * np.sin(alt) + np.cos(
        gw_data["altitude"]
    ) * np.cos(alt) * np.cos(gw_data["azimuth"] - az)
    cos_angular_distance[cos_angular_distance > 1] = 1
    cos_angular_distance[cos_angular_distance < -1] = -1
    angular_distance = np.arccos(cos_angular_distance) * 180 / np.pi

    deviation_sky_location = angular_distance**2 / ((5) ** 2)
    # deviation_inc = (np.cos(inc_source) - np.cos(inclination))**2/0.1**2
    deviation_distance = (gw_data["distance"] - distance) ** 2 / (distance / 10) ** 2
    deviation_mass = ((gw_data["mass1"] - mass1) + (gw_data["mass2"] - mass2)) ** 2 / (
        (mass1 + mass2) * 0.2
    ) ** 2

    total_deviation = deviation_sky_location + deviation_distance + deviation_mass

    count = 0
    deviation_sorted = np.argsort(total_deviation)
    index = deviation_sorted[count]
    while gw_data["far_gstlal"][index] >= 2 or gw_data["far_mbta"][index] >= 2:
        count += 1
        if count == len(gw_data["gpstime"]):
            return np.inf
        else:
            index = deviation_sorted[count]
    return np.min(
        [
            (gw_data["far_gstlal"][index] <= 2) * gw_data["far_gstlal"][index],
            (gw_data["far_mbta"][index] <= 2) * gw_data["far_mbta"][index]
        ]
    )

class IceCubeNeutrino(BaseModel):
    """Class for IceCube's neutrino detections."""
    mjd: float = Field(..., description="Detection time of the neutrino in MJD units.")
    ra: float = Field(..., description="Right ascension angle of the neutrino. [Deg]")
    dec: float = Field(..., description="Declination angle of the neutrino. [Deg]")
    epsilon: float = Field(..., description="Reconstructed energy ofthe neutrino. [GeV]")
    sigma: float = Field(..., description="Uncertainty radius of neutrino detection. [Deg]")

    def gps(self):
        """Converts mjd time format into gps time used in GW detections."""
        import astropy.time
        return astropy.time.Time(self.mjd, format='mjd').gps
    
    def psf(self):
        """Returns PartialUniqSkymap of the neutrino detection as
        a Gaussian point spread function centered around the right
        ascension and declination with sigma uncertainty.
        
        Parameters
        ----------
        right_ascension: Right ascension angle of neutrino in floating
        number and degrees for unit.
        declination: Declination angle of neutrino in floating number and
        degrees for unit.
        sigma: Standard deviation provided by IceCube neutrino detection.
        """

        from hpmoc.psf import psf_gaussian
        return psf_gaussian(ra=self.ra, dec=self.dec, sigma=self.sigma)
    
    def full_skymap(self, skymap):
        """Full skymap as an array with same nside as the skymap parameter."""
        partialskymap = self.psf()
        return partialskymap.fill(nside=skymap.nside)
    
