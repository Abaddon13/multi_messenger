import numpy as np
import pandas as pd

from data_loading import load_neutrino_data

neutrino_data = load_neutrino_data()
dataframes_effectiveArea = neutrino_data["effective_areas"]
dataframes_events = neutrino_data["events"]


def P_signal_nu_t(t_nu, t_s):
    t_plus = 250
    t_minus = -250
    if t_minus <= t_nu - t_s <= t_plus:
        return (t_plus - t_minus) ** -1
    else:
        return 0


def P_source_loc_detection(
    right_ascension_nu,
    declination_nu,
    angular_error,
    right_ascension_source,
    declination_source,
):
    """Normal distribution of the sky location and the angular error."""
    angle_difference = (right_ascension_nu - right_ascension_source) ** 2 + (
        declination_nu - declination_source
    ) ** 2
    return np.exp(-angle_difference / (2 * angular_error**2)) / (
        2 * np.pi * angular_error**2
    )


def A_eff(energy_log10, declination):
    #     energy_log10 = np.log10(energy)
    df = dataframes_effectiveArea["IC86_II_effectiveArea"]
    condition = (
        (df["log10(E_nu/GeV)_min"] <= energy_log10)
        & (energy_log10 < df["log10(E_nu/GeV)_max"])
        & (df["Dec_nu_min[deg]"] <= declination)
        & (declination < df["Dec_nu_max[deg]"])
    )
    effective_area = df[condition]
    return effective_area.iloc[0]["A_Eff[cm^2]"]


def P_signal_nu_source(declination_source):
    """Monte-Carlo integration of the source parameter distribution
    of sky location for the high energy neutrinos."""
    df = dataframes_effectiveArea["IC86_II_effectiveArea"]
    condition = (df["Dec_nu_min[deg]"] <= declination_source) & (
        declination_source < df["Dec_nu_max[deg]"]
    )
    filtered_df = df[condition]
    filtered_df = filtered_df[filtered_df.columns[:]].to_numpy()
    areas_top = []
    areas_bottom = []
    for row in filtered_df:
        d_epsilon = 0.2
        epsilon = (row[1] - row[0]) / 2
        d_dec = row[3] - row[2]
        A_eff = row[4]
        area = d_epsilon * d_dec * A_eff * epsilon**-2  # Area under the rectangle
        areas_top.append(area)
    integral_top = np.sum(areas_top)

    df = df[df.columns[:]].to_numpy()
    for row in df:
        d_epsilon = 0.2
        epsilon = (row[1] - row[0]) / 2
        d_dec = row[3] - row[2]
        A_eff = row[4]
        area = d_epsilon * d_dec * A_eff * epsilon**-2  # Area under the rectangle
        areas_bottom.append(area)
    integral_bottom = np.sum(areas_bottom)

    return integral_top / integral_bottom


def P_signal_nu_epsilon(epsilon_nu):
    """Monte-Carlo integration of the energy distributions for
    the high energy neutrinos. Returns the probability of getting
    a certain energy."""
    df = dataframes_effectiveArea["IC86_II_effectiveArea"]
    condition = (df["log10(E_nu/GeV)_min"] <= epsilon_nu) & (
        epsilon_nu < df["log10(E_nu/GeV)_max"]
    )
    filtered_df = df[condition]
    filtered_df = filtered_df[filtered_df.columns[:]].to_numpy()
    areas_top = []
    areas_bottom = []
    for row in filtered_df:
        d_epsilon = 0.2
        d_dec = row[3] - row[2]
        A_eff = row[4]
        P_source = P_signal_nu_source(row[2] + 1)
        area = (
            d_epsilon * d_dec * A_eff * P_source * epsilon_nu**-2
        )  # Area under the rectangle
        areas_top.append(area)
    integral_top = np.sum(areas_top)

    df = df[df.columns[:]].to_numpy()
    for row in df:
        d_epsilon = 0.2
        epsilon = (row[1] - row[0]) / 2
        d_dec = row[3] - row[2]
        A_eff = row[4]
        P_source = P_signal_nu_source(row[2] + 1)
        area = (
            d_epsilon * d_dec * A_eff * P_source * epsilon**-2
        )  # Area under the rectangle
        areas_bottom.append(area)
    integral_bottom = np.sum(areas_bottom)

    return integral_top / integral_bottom


def P_sigma_nu_E(epsilon_nu):
    """Epsilon nu is in the units of log(E_nu/GeV)"""
    df = dataframes_events["IC86_VII_exp-1"]
    binwidth = 0.01
    lower_bound = epsilon_nu - binwidth
    upper_bound = epsilon_nu + binwidth

    bin_data = [
        epsilon
        for epsilon in df["log10(E/GeV)"]
        if lower_bound <= epsilon <= upper_bound
    ]

    probability = len(bin_data) / len(df["log10(E/GeV)"])
    return probability


def P_skyloc_source(right_ascension, declination):
    """Just checks the angles if they are in the spherical sky map ranges
    and returns a uniform distribution over the entire sky."""
    if (0 <= right_ascension <= 360) & (-90 <= declination <= 90):
        return (4*np.pi)**-1
    return 0


def P_skyloc_data(declination, epsilon_nu):
    """Returns the probability of the given sky location and energy level
    in log10 scale from the data so can be used for the signal hypothesis."""
    df = dataframes_events["IC86_VII_exp-1"]
    condition_epsilon = (df["log10(E/GeV)"] <= epsilon_nu + 0.01) & (
        epsilon_nu - 0.01 <= df["log10(E/GeV)"]
    )
    condition_dec = (df["Dec[deg]"] <= declination + 1) & (
        declination - 1 <= df["Dec[deg]"]
    )
    condition = condition_epsilon & condition_dec
    filtered_df = df[condition]
    return len(filtered_df) if len(filtered_df) != 0 else 0


def P_skyloc_Aeff(declination, epsilon_nu):
    """Returns the probability of the given sky location and energy level
    using the effective area."""
    df = dataframes_effectiveArea["IC86_II_effectiveArea"]
    condition_epsilon = (df["log10(E_nu/GeV)_min"] <= epsilon_nu) & (
        epsilon_nu <= df["log10(E_nu/GeV)_max"]
    )
    condition_declination = (df["Dec_nu_min[deg]"] <= declination) & (
        declination <= df["Dec_nu_max[deg]"]
    )
    condition = condition_epsilon & condition_declination
    filtered_df = df[condition]
    filtered_df = filtered_df[filtered_df.columns[:]].to_numpy() 
    effective_area = filtered_df[0][4]
    return effective_area * (1/epsilon_nu**2) * (4*np.pi)**-1
