from pathlib import Path

import affine
import geopandas as gpd
import numpy as np
import rasterio
import rasterio.warp


def to_centroids(rast, nodata=0, to_crs=None):
    """Convert a raster input file to centroids.

    Returns a `geopandas.GeoDataFrame` with centroids of the input raster
    as the geometry and an additional column for the values of every
    input band.

    Parameters
    ----------
    rast : path_like
    nodata : int
        Range: 0 - 255
    to_crs : int
        EPSG code

    Returns
    -------
    gdf : geopoandas.GeoDataFrame
    """

    with rasterio.open(rast, 'r') as src:
        # returns a 3d np.ndarray (n_bands, rows, cols)
        arr = src.read()
        bands = arr.shape[0]
        rows = range(arr.shape[1])
        cols = range(arr.shape[2])
        crs = src.crs
        crs = crs.to_epsg()

        # returns an np.ndarray of same shape as input with Boolean values
        # True where input raster has a `nodata` value in every band
        mask = sum(arr) == nodata

        # create empty arrays for coordinates and every band
        xs, ys = [], []
        properties = [[] for _ in range(bands)]

        # get xy.values and band values where raster is not masked
        for r in rows:
            for c in cols:
                if not mask[r, c]:
                    x, y = src.xy(r, c, offset='center')
                    for i in range(bands):
                        properties[i].append(arr[i][r][c])
                    xs.append(x)
                    ys.append(y)

        gdf = gpd.GeoDataFrame(geometry=gpd.points_from_xy(xs,
                                                           ys,
                                                           crs=crs))

        if to_crs is not None:
            gdf.to_crs(epsg=to_crs, inplace=True)

        # add columns with raster band values to gdf
        for i in range(bands):
            gdf[f'b{i+1}'] = properties[i]

    print('epsg:', crs)
    print('n_points:', len(xs))

    return gdf


def reproject_raster(inpath, outpath, to_crs, skip_existing=True):
    """Reproject a raster file.

    Code taken from: https://www.earthdatascience.org/courses/use-data-open-source-python/intro-raster-data-python/raster-data-processing/reproject-raster/

    Parameters
    ----------
    inpath : str
        Path to the source raster file.
    outpath : str
        Path to the new reprojected raster file.
    to_crs : int
        EPSG code
    skip_existing : bool

    Returns
    -------
    None
    """
    import warnings
    message = f'This function is deprecated. Please use function "{reproject.__name__}" instead.'
    warnings.warn(message, DeprecationWarning, stacklevel=2)

    if skip_existing and Path(outpath).exists():
        print(f'The target file {outpath} already exists. [Skipping]')
        return None

    dst_crs = to_crs

    with rasterio.open(inpath) as src:
        dst_transform, width, height = rasterio.warp.calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds)
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': dst_crs,
            'transform': dst_transform,
            'width': width,
            'height': height
        })

        print(f'Reprojecting from {src.crs} to EPSG:{dst_crs}...')
        with rasterio.open(outpath, 'w', **kwargs) as dst:
            for i in range(1, src.count + 1):
                rasterio.warp.reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dst_transform,
                    dst_crs=dst_crs,
                    resampling=rasterio.warp.Resampling.nearest)

    print('---Reprojection successful---')
    return None


def reproject(array=None, profile=None, raster=None, from_crs=None, to_crs=None, driver='GTiff'):
    """Reproject a raster file.

    Takes either a ndarray + profile or a path to a raster file.
    Returns a ndarray + profile.
    """
    if raster is not None:
        with rasterio.open(raster) as src:
            array = src.read(masked=True)
            profile = src.profile

    elif array is None or profile is None:
        raise ValueError('Please supply either a raster file or a ndarray and '
                         'a profile')

    src_crs = profile['crs']
    if from_crs is not None:
        src_crs = rasterio.crs.CRS.from_epsg(from_crs)
    src_height = profile['height']
    src_width = profile['width']
    src_transform = profile['transform']
    src_nodata = profile['nodata']
    src_bounds = rasterio.transform.array_bounds(src_height,
                                                 src_width,
                                                 src_transform)

    print(f'Reprojecting from {src_crs} to EPSG:{to_crs}...')

    dst_transform, dst_width, dst_height = rasterio.warp.calculate_default_transform(
        src_crs, to_crs, src_width, src_height, *src_bounds)

    dst_profile = profile.copy()
    dst_profile.update({
        'crs': to_crs,
        'transform': dst_transform,
        'width': dst_width,
        'height': dst_height,
        'driver': driver
    })

    dst = np.zeros((array.shape[0], dst_height, dst_width), array.dtype)

    rasterio.warp.reproject(
        source=array,
        destination=dst,
        src_transform=src_transform,
        src_crs=src_crs,
        src_nodata=src_nodata,
        dst_transform=dst_transform,
        dst_crs=to_crs,
        dst_nodata=src_nodata,
        resampling=rasterio.warp.Resampling.nearest)

    print('---Reprojection successful---')
    return dst, dst_profile


def rescale_align(array=None, profile=None, vector=None, resolution=100, resampling='nearest'):
    '''Rescale and align raster data.

    The raster data is aligned with the bounding box of an input vector.'''

    if resampling == 'nearest':
        resampling = rasterio.warp.Resampling.nearest
    elif resampling == 'bilinear':
        resampling = rasterio.warp.Resampling.bilinear
    elif resampling == 'cubic':
        resampling = rasterio.warp.Resampling.cubic
    elif resampling == 'mode':
        resampling = rasterio.warp.Resampling.mode
    elif resampling == 'average':
        resampling = rasterio.warp.Resampling.average
    else:
        raise ValueError('Please specify a valid resampling method.')

    src_array = array
    src_profile = profile

    # Get source attributes
    src_transform = src_profile['transform']
    src_crs = src_profile['crs']
    src_nodata = src_profile['nodata']

    # Output image resolution
    yres = xres = resolution

    # Output image transformation (Resize & Align)
    dst_bounds = vector.total_bounds.tolist()
    left, bottom, right, top = dst_bounds
    dst_width = (right - left) // xres
    dst_height = (top - bottom) // yres
    dst_transform = affine.Affine(xres, 0.0, left,
                                  0.0, -yres, top)

    # Create new array for the output
    dst_array = np.zeros((src_array.shape[0],
                         int(dst_height),
                         int(dst_width)),
                         src_array.dtype)

    # Resize & Align array and write to output array
    rasterio.warp.reproject(
        source=src_array,
        destination=dst_array,
        src_transform=src_transform,
        src_crs=src_crs,
        src_nodata=src_nodata,
        dst_transform=dst_transform,
        dst_crs=src_crs,
        dst_nodata=src_nodata,
        resampling=resampling)

    # Update Metadata
    dst_profile = src_profile.copy()
    dst_profile['transform'] = dst_transform
    dst_profile['width'] = dst_width
    dst_profile['height'] = dst_height

    print('---Rescaling & Aligning successful---')
    return dst_array, dst_profile
