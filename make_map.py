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
        if i.endswith('.xls') or i.endswith('.xlsx'):
            xls = i
            break
    filename = None
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

    rename = {
        'DateRep': 'date',
        'Day': 'day',
        'Month': 'month',
        'Year': 'year',
        'Cases': 'new_cases',
        'Deaths': 'new_deaths',
        'Countries and territories': 'country',
        'GeoId': 'geoid',
    }
    data = data.rename(rename, axis='columns')
    dates = list(sorted(data['date'].unique()))
    for key in ('country', 'geoid'):
        data[key] = data[key].str.lower()
    # Replace "_" by space in country name:
    data['country'] = data['country'].str.replace('_',' ')
    return data, dates


def read_population(filename='population.csv'):
    """Read population data."""
    data = pd.read_csv(filename)
    data['Region'] = data['Region'].str.lower()
    return data


def add_cumulative(raw_data, dates):
    """Add cumulative data."""
    # Sort data by date and country:
    # Get all countries:
    countries = list(sorted(raw_data['country'].unique()))
    # For each country, check if we are missing dates:
    missing_data = {i: [] for i in raw_data.columns}
    for country in countries:
        datai = raw_data.loc[raw_data['country'] == country]
        datesi = datai['date'].values
        missing_dates = [i for i in dates if i not in datesi]
        # Add missing data with zeros:
        for i in missing_dates:
            missing_data['date'].append(i)
            missing_data['country'].append(country)
            missing_data['new_cases'].append(0)
            missing_data['new_deaths'].append(0)
            for key in missing_data:
                if key not in {'date', 'country', 'new_cases', 'new_deaths'}:
                    missing_data[key].append(datai[key].values[-1])
        # Sort this data on the date:
    missing_data = pd.DataFrame(missing_data)
    raw_data2 = raw_data.copy()
    raw_data2 = raw_data2.append(missing_data, verify_integrity=True,
                                 ignore_index=True)
    data = raw_data2.sort_values(by=['country', 'date'])
    data = data.reset_index(drop=True)
    data['sum_cases'] = float('nan')
    data['sum_deaths'] = float('nan')
    for country in countries:
        datai = data.loc[data['country'] == country]
        cases = datai['new_cases'].cumsum()
        deaths = datai['new_deaths'].cumsum()
        data.loc[data['country'] == country, 'sum_cases'] = cases
        data.loc[data['country'] == country, 'sum_deaths'] = deaths
    return data


def norm_population(data, population):
    """Normalize data by population."""
    countries = list(sorted(data['country'].unique()))
    data['sum_cases_per_capita'] = float('nan')
    data['sum_deaths_per_capita'] = float('nan')
    data['new_cases_per_capita'] = float('nan')
    data['new_deaths_per_capita'] = float('nan')
    for country in countries:
        pop = population.loc[population['Region'] == country]
        if len(pop) != 1:
            continue
        capita = pop['Population_2020'].values[0]  # in thousands
        capita /= 100 # in hundred thousands 
        datai = data.loc[data['country'] == country]
        cases = datai['sum_cases'].values
        deaths = datai['sum_deaths'].values
        new_cases = datai['new_cases'].values
        new_deaths = datai['new_deaths'].values
        data.loc[
            data['country'] == country, 'sum_cases_per_capita'
        ] = cases / capita
        data.loc[
            data['country'] == country, 'sum_deaths_per_capita'
        ] = deaths / capita
        data.loc[
            data['country'] == country, 'new_cases_per_capita'
        ] = new_cases / capita
        data.loc[
            data['country'] == country, 'new_deaths_per_capita'
        ] = new_deaths / capita


def print_missing_countries(data, country_map):
    """Print info on countries we are missing in the geo json data."""
    missing = []
    fet = {key.lower() for key in country_map}
    for i in list(sorted(data['country'].unique())):
        if i not in fet:
            missing.append(i)
    if missing:
        print('Missing geo json features:')
        for i in missing:
            print('\t- {}'.format(i))
    return missing
