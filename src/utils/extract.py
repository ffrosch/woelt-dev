# import fiona
import geopandas as gpd
import matplotlib.pyplot as plt
import rasterio
import rasterio.mask as riomask

from math import ceil, floor
from rasterio.io import MemoryFile
from rasterio.plot import show as rioshow
from shapely.geometry import mapping, Polygon


def bbox_polygon(lx, ly, ux, uy):
    return Polygon([[lx, ly], [lx, uy], [ux, uy], [ux, ly]])


def clip_old(rast, shp, out=None, nodata=0, all_touched=True, plot=True):
    """Clip all bands of a raster input file with a polygon mask.

    The output will be a rectangular raster which matches the bounding box of
    the polygon mask. All pixels outside of the mask but within the bounding
    box will be set to 0 by default.

    Parameters
    ----------
    rast : path_like
        str or pathlike object which points to a GeoTIFF.
    shp : path_like or geopandas.GeoDataFrame
        str or pathlike object which points to a Shapefile.
    out : path_like, optional
        Output path for the clipped dataset. Optional.
    nodata : int
        Value for nodata pixels.
    all_touched : bool
        Include pixels that are intersected by the polygon? Default is `True`.

    Returns
    -------
    rast : numpy.ndarray
        A `rasterio raster object` with type `numpy.ndarray`.
    transform : dict
        Metadata that defines the cartographic transformation.
    """
    import warnings
    message = f'This function is deprecated. Please use function "{clip.__name__}" instead.'
    warnings.warn(message, DeprecationWarning, stacklevel=2)

    if type(shp) == str:
        # with fiona.open(shp, 'r') as shapefile:
        #     shapes = [feature['geometry'] for feature in shapefile]
        gdf = gpd.read_file(shp)

    elif type(shp) == gpd.geodataframe.GeoDataFrame:
        gdf = shp

    else:
        raise ValueError('Please specify a valid path or GeoDataFrame.')

    shapes = [feat['geometry'] for feat in gdf.geometry.__geo_interface__['features']]

    with rasterio.open(rast) as src:
        in_image = src.read()
        in_transform = src.transform
        out_meta = src.meta
        out_image, out_transform = riomask.mask(src,
                                                shapes,
                                                all_touched=True,
                                                crop=True,
                                                nodata=nodata)
        out_meta.update({"driver": "GTiff",
                         "height": out_image.shape[1],
                         "width": out_image.shape[2],
                         "transform": out_transform})

    if out is not None:
        with rasterio.open(out, "w", **out_meta) as dest:
            dest.write(out_image)
        print(f'Successfully saved clipped raster to {out}')

    if plot:
        fig, ax = plt.subplots(ncols=2)
        rioshow(in_image, transform=in_transform, ax=ax[0])
        rioshow(out_image, transform=out_transform, ax=ax[1])
        gdf.plot(facecolor='None', edgecolor='red', ax=ax[0])

    return out_image, out_meta


def clip(array=None, profile=None, vector=None, raster=None, all_touched=True,
         driver='GTiff', masked=True, extent=False):
    """Clip a raster file.

    Takes either a ndarray + profile or a path to a raster file.
    Also takes a vector as path or GeoDataFrame.
    Returns a ndarray + profile.
    """
    if type(vector) == str:
        # with fiona.open(shp, 'r') as shapefile:
        #     shapes = [feature['geometry'] for feature in shapefile]
        gdf = gpd.read_file(vector)

    elif type(vector) == gpd.geodataframe.GeoDataFrame:
        gdf = vector

    else:
        raise ValueError('Please specify a valid vector path or GeoDataFrame.')

    if raster is not None:
        with rasterio.open(raster) as src:
            array = src.read(masked=masked)
            profile = src.profile

    elif array is None or profile is None:
        raise ValueError('Please supply either a raster file or a ndarray and '
                         'a profile')

    if extent:
        polygon = bbox_polygon(*gdf.total_bounds)
        shapes = [mapping(polygon)]
    else:
        shapes = [feat['geometry'] for feat in gdf.geometry.__geo_interface__['features']]

    memfile = MemoryFile()
    with memfile.open(**profile) as mem:
        mem.write(array)
        dst_array, dst_transform = riomask.mask(mem,
                                                shapes,
                                                all_touched=all_touched,
                                                crop=True,
                                                filled=masked)

    dst_profile = profile.copy()
    dst_profile.update({"height": dst_array.shape[1],
                        "width": dst_array.shape[2],
                        "transform": dst_transform,
                        "driver": driver})

    print('---Clipping successful---')
    return dst_array, dst_profile


def subset(raster, gdf):
    with rasterio.open(raster) as src:
        # Round to avoid error where the output raster is falsely offset
        # an Alternative solution might be:
        #     transform = rasterio.windows.transform(window, dataset.transform)
        llx, lly, urx, ury = gdf.total_bounds
        bounds = (floor(llx), floor(lly), ceil(urx), ceil(ury))
        win = src.window(*bounds)

        win_profile = src.profile.copy()
        win_profile['transform'] = src.window_transform(win)
        win_profile['height'] = win.height
        win_profile['width'] = win.width

        win_array = src.read(window=win)

        return win_array, win_profile
