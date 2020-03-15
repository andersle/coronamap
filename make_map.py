# Copyright (c) 2020, Anders Lervik.
# Distributed under the MIT License. See LICENSE for more info.
"""Functions for downloading the raw data and preparing for making a map."""
import pathlib
import requests
from lxml import html
import pandas as pd
from map_basics import (
    load_json_file,
)


def get_url_xls():
    """Get url of target xls file."""
    base = (
        'https://www.ecdc.europa.eu/en/publications-data/'
        'download-todays-data-geographic-distribution-covid-19-cases-worldwide'
    )
    page = requests.get(base)
    tree = html.fromstring(page.content)
    xpath = '//a/@href'
    xls = None
    for i in tree.xpath(xpath):
        if i.endswith('.xls'):
            xls = i
            break
    if xls is not None:
        filename = pathlib.Path(xls).name
    return xls, filename


def download_if_needed(url, filename, force=False, progress=None):
    """Download the given file."""
    if force or not pathlib.Path(filename).exists():
        print('Downloading: {}'.format(url))
        response = requests.get(url, stream=True)
        size = int(response.headers.get('content-length', 0))
        with open(filename, 'wb') as output:
            if progress is None:
                for data in response.iter_content():
                    output.write(data)
            else:
                for data in progress(response.iter_content(), total=size):
                    output.write(data)


def load_countries():
    """Load country geo json files for a given resolution."""
    base_path = pathlib.Path(__file__).resolve().parent
    path = base_path.joinpath('countries', '50m', 'world.geo.json.gz')
    data = load_json_file(path)

    country_map = {}

    for item in data['features']:
        name = item['properties']['name']
        country_map[name] = item['id']
    return None, data, country_map


def read_raw_data(filename):
    """Read the raw data from a xls file."""
    data = pd.read_excel(filename)
    dates = list(sorted(data['DateRep'].unique()))
    for key in ('CountryExp', 'GeoId', 'Gaul1Nuts1', 'EU'):
        data[key] = data[key].str.lower()
    return data, dates


def add_cumulative(raw_data, dates):
    """Add cumulative data."""
    # Sort data by date and country:
    # Get all countries:
    countries = list(sorted(raw_data['CountryExp'].unique()))
    # For each country, check if we are missing dates:
    missing_data = {
        'DateRep': [],
        'CountryExp': [],
        'NewConfCases': [],
        'NewDeaths': [],
        'GeoId': [],
        'Gaul1Nuts1': [],
        'EU': [],
    }
    for country in countries:
        datai = raw_data.loc[raw_data['CountryExp'] == country]
        datesi = datai['DateRep'].values
        missing = [i for i in dates if i not in datesi]
        # Add missing data with zeros:
        for i in missing:
            missing_data['DateRep'].append(i)
            missing_data['CountryExp'].append(country)
            missing_data['NewConfCases'].append(0)
            missing_data['NewDeaths'].append(0)
            missing_data['GeoId'].append(datai['GeoId'].values[-1])
            missing_data['Gaul1Nuts1'].append(datai['Gaul1Nuts1'].values[-1])
            missing_data['EU'].append(datai['EU'].values[-1])
        # Sort this data on the date:
    missing_data = pd.DataFrame(missing_data)
    raw_data2 = raw_data.copy()
    raw_data2 = raw_data2.append(missing_data, verify_integrity=True,
                                 ignore_index=True)
    data = raw_data2.sort_values(by=['CountryExp', 'DateRep'])
    data = data.reset_index(drop=True)
    data['cases'] = float('nan')
    data['deaths'] = float('nan')
    for country in countries:
        datai = data.loc[data['CountryExp'] == country]
        cases = datai['NewConfCases'].cumsum()
        deaths = datai['NewDeaths'].cumsum()
        data.loc[data['CountryExp'] == country, 'cases'] = cases
        data.loc[data['CountryExp'] == country, 'deaths'] = deaths
    return data


def print_missing_countries(data, country_map):
    """Print info on countries we are missing in the geo json data."""
    missing = []
    fet = {key.lower() for key in country_map}
    for i in list(sorted(data['CountryExp'].unique())):
        if i not in fet:
            missing.append(i)
    if missing:
        print('Missing geo json features:')
        for i in missing:
            print('\t- {}'.format(i))
    return missing
