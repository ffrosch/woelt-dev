# Standard library imports
from pathlib import Path

# Third party imports
import colorcet as cc
import datashader as ds
import geopandas as gpd
import holoviews as hv
import holoviews.operation.datashader as hd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import seaborn as sns
import spatialpandas as spd
from math import ceil, sqrt
from rasterio.plot import show as rioshow
from sklearn.ensemble import ExtraTreesClassifier
# from datashader import transfer_functions as tf

# suppress warnings about initial parquet implementation
import warnings
warnings.filterwarnings('ignore',
                        message='.*initial implementation of Parquet.*')
warnings.filterwarnings('ignore', category=UserWarning)

hv.extension("bokeh", "matplotlib")
hd.shade.cmap = ["lightblue", "darkblue"]

#sns.set()  # for plot styling


def feature_importances(X, y, figsize=(10, 10)):
    # Compute the impurity-based feature importances with an ExtraTreesClassifier
    model = ExtraTreesClassifier()
    model.fit(X, y)

    importances = pd.Series(model.feature_importances_, index=X.columns)
    std = np.std([tree.feature_importances_ for tree in model.estimators_], axis=0)
    indices = np.argsort(importances)[::-1]

    # feat_importances = pd.Series(model.feature_importances_, index=X.columns)
    # feat_importances.nlargest(20).plot(kind='barh')
    # plt.style.use('ggplot')
    sns.set_theme()

    fig, ax = plt.subplots(figsize=figsize)
    plt.title("Feature importances")
    ax.barh(range(X.shape[1]), importances[indices],
            color="tab:blue", xerr=std[indices], align="center")
    plt.yticks(range(X.shape[1]), importances.index[indices])
    plt.ylim([-1, X.shape[1]])
    plt.show()

    sns.reset_orig()


def multiplot_raster(folder=None, files=None, arrays=None):
    in_memory = False

    if folder is not None:
        folder = Path(folder)
        data = list(folder.glob('*.tif'))
    elif files is not None:
        data = [Path(file) for file in files]
    elif arrays is not None:
        data = arrays
        in_memory = True
    else:
        raise ValueError('No data provided.')

    nplots = len(data)
    ncols = nrows = ceil(sqrt(nplots))

    fig, ax = plt.subplots(nrows=nrows, ncols=ncols, sharex=True, sharey=True, figsize=(16,16))
    ax = ax.flatten()

    for i, img in enumerate(data):
        _ax = ax[i]

        if not in_memory:
            _ax.set_title(f'{img.name}')
            with rasterio.open(img) as src:
                img = src.read(masked=True)

        rioshow(img, ax=_ax)

    if nplots < len(ax):
        for _ in ax[nplots:]:
            _.set_axis_off()

    plt.tight_layout()


def polygons(gdf, label='', geometry='geometry', col=None, agg=ds.any):
    """Return a holoviews plot.

    Multiple holoviews plots can be collected in a list and plotted with
    hv.Layout(list_of_plots).cols(3).

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
    label : str
    geometry : geometry column
    col : str
        Column on which the datashader data aggregation will be done.
        The default is `None`.
    agg : datashader aggregation function
        The default is `ds.any`.

    Returns
    -------
    shd : holoviews plot
    """
    hv.output(backend="matplotlib")

    sgdf = spd.GeoDataFrame(gdf)
    cvs = ds.Canvas()

    if col is not None:
        agg = cvs.polygons(sgdf, geometry, agg=agg(col))
    else:
        agg = cvs.polygons(sgdf, geometry, agg=agg())

    shd = hd.shade(hv.Image(agg, label=label))

    return shd


def region(vector, raster, cmap='rainbow', boundary='red', band=1):
    """Quickly plot a subregion from a rasterdataset.

    The subregion is defined by the bounding box of the supplied vector.
    Colourmaps will primarily be obtained from the colorcet library.

    Parameters
    ----------
    vector : geopandas.GeoDataFrame or path_like object
    raster : rasterio.io.DatasetReader or path_like object
    cmap : colormap
        colormap for the raster data.
        Continuous data: e.g. colorwheel, rainbow, fire
        Categorical data: e.g. glasbey
    boundary : colorname
        color for the vector data

    Returns
    -------
    ax : matplotlib plot
    """
    if isinstance(vector, str):
        if Path(vector).suffix == '.parquet':
            gdf = gpd.read_parquet(vector)
        else:
            gdf = gpd.read_file(vector)
    else:
        gdf = vector

    if isinstance(raster, str):
        rast_file = rasterio.open(raster)
    else:
        rast_file = raster

    if cmap in cc.cm:
        cmap = cc.cm[cmap]

    # matplotlib and geographic packages like rasterio and geopandas use
    # different ordering conventions for their bounding box information.
    # geographic information systems (bounds): (west, south, north, east)
    # matplotlib (extent): (west, east, south, north)
    gdf_bounds = gdf.total_bounds
    gdf_extent = gdf_bounds[[0, 2, 1, 3]]

    # Subsetting raster data in rasterio is easiest to do before it is
    # read into memory (although it is possible to do so after read()).
    # Subsetting data requires a rasterio.windows.Window object to be built
    # that describes the area to focus on. There are many helper functions
    # to build windows, but the simplest is: rast_file.window
    # A window can easily be build by unpacking bounds obtained from a gdf
    rast_window = rast_file.window(*gdf_bounds)

    # Now we can read in our data within the desired region
    rast = rast_file.read(band, window=rast_window)

    plt.imshow(rast, cmap=cmap, extent=gdf_extent)
    gdf.boundary.plot(ax=plt.gca(), color=boundary)
