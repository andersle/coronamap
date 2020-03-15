# Copyright (c) 2020, Anders Lervik.
# Distributed under the MIT License. See LICENSE for more info.
"""Create a map using folium."""
from functools import partial
import pathlib
import json
import gzip
import numpy as np
import folium
from folium.plugins import TimeSliderChoropleth
import branca.colormap as cm


COLORS = {
    'blue': '#1f77b4',
    'orange': '#ff7f0e',
    'green': '#2ca02c',
    'red': '#d62728',
    'purple': '#9467bd',
    'brown': '#8c564b',
    'pink': '#e377c2',
    'gray': '#7f7f7f',
    'yellow': '#bcbd22',
    'cyan': '#17becf',
}


def load_json_file(filename):
    """Load data from a json file."""
    data = {}
    print('Loading file "{}"'.format(filename))
    if '.gz' in filename.suffixes:
        with gzip.open(filename, 'rt') as zipfile:
            data = json.load(zipfile)
    else:
        with open(filename, 'r') as infile:
            data = json.load(infile)
    return data


COLOR_MAPS = load_json_file(
    pathlib.Path(cm.rootpath).joinpath('_schemes.json')
)


OPACITY = 0.7


def style_function_color_map(item, style_dict):
    """Style for geojson polygons."""
    feature_key = item['id']
    if feature_key not in style_dict:
        color = '#d7e3f4'
        opacity = 0.0
    else:
        color = style_dict[feature_key]['color']
        opacity = style_dict[feature_key]['opacity']
    style = {
        'fillColor': color,
        'fillOpacity': opacity,
        'color': '#262626',
        'weight': 0.5,
    }
    return style


def default_highlight_function(item):
    """Style for geojson highlighting."""
    return {'weight': 2.0, 'fillOpacity': OPACITY + 0.1}


def add_tiles_to_map(the_map):
    """Add default tiles to a folium map.

    Parameters
    ----------
    the_map : object like folium.folium.Map
        The map we are to add the tiles to.

    """
    folium.TileLayer('cartodbpositron').add_to(the_map)
    folium.TileLayer('openstreetmap').add_to(the_map)


def get_min_max(data, countries, log=True):
    """Get min/max for cases for selected countries."""
    min_value = 0.0
    max_value = 0.0
    for country in countries:
        datai = data.loc[data['CountryExp'] == country]
        if len(datai) == 0:
            continue
        values = datai['cases'].values
        if log:
            values = do_log(values)
        min_value = min(min_value, min(values))
        max_value = max(max_value, max(values))
    return min_value, max_value


def get_country_id(country, geojson):
    """Get id for countries."""
    for feature in geojson['features']:
        idx = feature['id']
        name = feature['properties']['name'].lower()
        if name == country.lower():
            return idx
    return None


def add_cases_to_geojson(data, geojson):
    """Add cases to the geojson properties field."""
    for feature in geojson['features']:
        name = feature['properties']['name'].lower()
        datai = data.loc[data['CountryExp'] == name]
        if len(datai) == 0:
            feature['properties']['cases'] = 'Missing data'
        else:
            feature['properties']['cases'] = datai['cases'].values[0]


def create_style(data, geojson, countries, color_map, log=False):
    """Create styles based on number of cases.

    Parameters
    ----------
    data : object like :class:`pandas.DataFrame`
        The data we are to present.
    geojson : dict
        The geo json data we are to display.
    color_map : object like :class:`branca.colormap.ColorMap`
        The color map we are to use.
    log : boolean
        If True, we will log-scale the data.

    Returns
    -------
    style_dict : dict
        A dict containing the styles (color, opacity) to use
        for the different geo json features.

    """
    style_dict = {}
    for country in countries:
        datai = data.loc[data['CountryExp'] == country]
        if len(datai) == 0:
            continue
        values = datai['cases'].values
        if log:
            values = do_log(values)
        # Get id for country:
        country_idx = get_country_id(country, geojson)
        if country_idx is None:
            continue
        style = []
        for val in values:
            opacity = 0 if np.isnan(val) else OPACITY
            color = '#ffffff'if np.isnan(val) else color_map(val)
            style.append(
                {
                    'color': color,
                    'opacity': opacity,
                }
            )
        style_dict[country_idx] = style
    return style_dict


def create_style_dicts(data, geojson, countries=None,
                       log=False, color_map_name='Reds_03',
                       min_value=None, max_value=None):
    """Create style dicts for the given countries.

    Parameters
    ----------
    data : object like :class:`pandas.DataFrame`
        The data we are to present.
    geojson : dict
        The geo json data we are to display.
    countries : list of strings, optional
        The countries we are to display. If None is given,
        all possible countries will be used.
    log : boolean, optional
        If True, we will log-scale the data.
    color_map_name : string, optional
        The name of the color maps we are to use.
    min_value : float, optional
        Minimum value for the color scale.
    max_value : float, optional
        Maximum value for the color scale.

    Returns
    -------
    style_dict : dictionary
        The style dicts created here.
    linear : object like :class:`branca.colormap.ColorMap`
        The created color map.

    """
    if countries is None:
        countries = list(sorted(data['CountryExp'].unique()))
    mini, maxi = get_min_max(data, countries, log=log)
    if min_value is None:
        min_value = mini
    if max_value is None:
        max_value = maxi
    # Set up color map:
    linear = cm.LinearColormap(
        COLOR_MAPS[color_map_name],
        vmin=min_value,
        vmax=max_value,
    )
    style_dict = create_style(data, geojson, countries, linear, log=log)
    return style_dict, linear


def create_folium_map(geojson, data, map_settings):
    """Create a folium map.

    Parameters
    ----------
    geojson : dict
        The geojson data to diplay.
    map_settings : dict
        A dict containing settings for initializing the map.

    Returns
    -------
    the_map : object like folium.folium.Map
        The map created here.

    """
    the_map = folium.Map(
        location=map_settings.get('center', [63.447, 10.422]),
        tiles=None,
        zoom_start=map_settings.get('zoom', 9),
    )
    add_tiles_to_map(the_map)

    title = map_settings.get('title', None)
    if title is not None:
        legend_html = '''
        <div style="position: fixed; bottom: 100px; left: 50px; z-index:9999;
        font-size:24px;"><b>{}</b>
        </div>
        '''.format(title)
        the_map.get_root().html.add_child(folium.Element(legend_html))

    use_logscale = map_settings.get('logscale', True)

    styles, color_map = create_style_dicts(
        data,
        geojson,
        countries=None,
        log=use_logscale,
        color_map_name=map_settings.get('color_map', 'Reds_03'),
        min_value=map_settings.get('min_value', None),
        max_value=map_settings.get('max_value', None),
    )
    # Limit to one style per country:
    style_dict = {}
    for key, val in styles.items():
        style_dict[key] = val[0]

    style_function = partial(
        style_function_color_map,
        style_dict=style_dict,
    )

    add_cases_to_geojson(data, geojson)

    tool = folium.GeoJsonTooltip(
        fields=['name', 'cases'],
        aliases=['Country', 'Cases'],
        style=('font-size: 14px;'),
        labels=True,
    )

    folium.GeoJson(
        geojson,
        name='Cases',
        style_function=style_function,
        highlight_function=default_highlight_function,
        tooltip=tool
    ).add_to(the_map)

    if use_logscale:
        color_map.caption = 'Cases (log2 scale)'
    else:
        color_map.caption = 'Cases'
    the_map.add_child(color_map)
    folium.LayerControl().add_to(the_map)
    return the_map


def extract_data_values(data, value_key):
    """Extract value from a pandas.DataFrame

    Parmeters
    ---------
    data : dict
        The raw data.
    value_key : string
        A column in data which contains the values we are to extract.

    Returns
    -------
    values : dict
        A dict where the keys are the id's found in data_key and
        the values are the correconding values from data_value.

    """
    values = {}
    for key in data:
        values[key] = data[key][value_key]
    return values


def do_log(values):
    """Apply log to the given values."""
    log = []
    for i in values:
        if i == 0:
            log.append(float('nan'))
        else:
            log.append(np.log2(i))
    return log


def create_folium_choropleth(geojson, data, map_settings):
    """Create a folium choropleth map.

    Parameters
    ----------
    geojson : dict
        A geojson layer to add to the map.
    data : dict
        The raw data to use for coloring.
    map_settings : dict
        A dict containing settings for initializing the map.

    Returns
    -------
    the_map : object like folium.folium.Map
        The map created here.

    """
    the_map = folium.Map(
        location=map_settings.get('center', [63.447, 10.422]),
        tiles='cartodbpositron',
        zoom_start=map_settings.get('zoom', 9),
    )

    use_logscale = map_settings.get('logscale', True)

    countries = list(sorted(data['CountryExp'].unique()))

    min_value, max_value = get_min_max(data, countries, log=use_logscale)
    # Create color map:
    color_map_name = map_settings.get('color_map', 'Reds_03')
    color_map = cm.LinearColormap(
        COLOR_MAPS[color_map_name],
        vmin=min_value,
        vmax=max_value,
    )
    # Create styles for selected countries:
    styles = create_style(data, geojson, countries, color_map,
                          log=use_logscale)
    dates = (data['DateRep'].unique().astype(int) // 10**9).astype('U10')
    # Restructure style dict to contain dates:
    style_dict = {}
    for key, val in styles.items():
        style_dict[key] = {}
        for datei, vali in zip(dates, val):
            style_dict[key][datei] = vali

    slider = TimeSliderChoropleth(
        geojson,
        styledict=style_dict,
    ).add_to(the_map)

    if use_logscale:
        color_map.caption = 'Cases (log2 scale)'
    else:
        color_map.caption = 'Cases'
    the_map.add_child(color_map)
    return the_map
