# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Read the results the Fitter scripts write, without ROOT.

FitparameterValues_<tag>_DeepTau_<era>-13TeV_<region>.txt (written by TauES_ID/makecombinedfitTES_SF.py, option 3)
has one `name: value` line per parameter:

    tes_DM0_pt1: 0.987000
    tes_DM0_pt1_1sigma_low: 0.981000
    tes_DM0_pt1_1sigma_high: 0.993000
    tid_SF_DM0_pt1: 0.912000
    ...                                   (followed by the nuisance parameters, which are ignored here)

Public API:
  read_fit_values(text, region) -> list of {region, poi, value, low, high}
"""

__all__ = ['read_fit_values', 'POIS']


POIS = ('tes', 'tid_SF')  # the parameters of interest of the option-3 fit, per region


def read_fit_values(text, region):
    """The best-fit value and 1-sigma interval of each parameter of interest of one region. A missing interval
    (no grid point within 1 sigma) gives None for low and high; a missing parameter is left out."""
    values = {}
    for line in text.splitlines():
        name, separator, value = line.partition(':')
        if not separator:
            continue
        try:
            values[name.strip()] = float(value)
        except ValueError:
            continue
    rows = []
    for poi in POIS:
        name = "%s_%s" % (poi, region)
        if name in values:
            rows.append({'region': region, 'poi': poi, 'value': values[name],
                         'low': values.get(name + '_1sigma_low'), 'high': values.get(name + '_1sigma_high')})
    return rows
