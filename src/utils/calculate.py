import geopandas as gpd
import numpy as np
import shapely
from tqdm import tqdm

# suppress warnings about initial parquet implementation
import warnings
warnings.filterwarnings('ignore', message='.*initial implementation of Parquet.*')


def meff(lines, boundary, mask):
    """Calculate the modified effective mesh size.

    Merges the lines with the boundary to create a "closed" area.
    The modified effective mesh size accounts for arbitrary
    boundaries within the mask. With the CBC (Cross Boundary Connections)
    these boundaries do not influence the effective mesh size.

    Parameters
    ----------
    lines : geopoandas.GeoDataFrame (Lines)
    boundary : geopoandas.GeoDataFrame (Polygon)
    mask : geopoandas.GeoDataFrame (Polygons)

    Returns
    -------
    mask : geopoandas.GeoDataFrame
        mask contains a new column "meff". The effective mesh
        size in km² for each polygon
    """
    # Formula for meff CBC: https://link.springer.com/article/10.1007/s10980-006-9023-0
    # !!! Don't iterate over a pandas dataframe, instead vectorize: https://stackoverflow.com/a/55557758/9152905

    # meff is calculated based on the cartesian measurement units of the projection -> m² for epsg:3035
    # meff is stored as km² instead of m²

    # Create a continuous border so that the areas between the roads closest to the border and the border are also considered.
    # consider to merge lines (they are slightly extended for the process) before using unary_union
    # see: https://gis.stackexchange.com/a/312215/89529

    crs = mask.crs.to_epsg()
    mask = mask.copy()
    mask['meff'] = np.nan

    lines.geometry.append(boundary.boundary)
    lines = gpd.GeoDataFrame(geometry=gpd.GeoSeries(lines.unary_union), crs=crs)

    # Transform lines to polygons
    result, dangles, cuts, invalids = list(shapely.ops.polygonize_full(lines.geometry))
    lines_polygonized = gpd.GeoDataFrame(geometry=gpd.GeoSeries(result, crs=crs))

    patches = lines_polygonized.explode()
    patches_sindex = patches.sindex

    for cell in tqdm(mask.itertuples(), total=len(mask), desc='Calculation of the meff_cbc value'):
        fragments_sum = 0

        fragment_candidates_idx = list(patches_sindex.intersection(cell.geometry.bounds))
        fragment_candidates = patches.iloc[fragment_candidates_idx]
        fragments = fragment_candidates[fragment_candidates.intersects(cell.geometry)]

        # this should also be doable with fragments.intersection and pandas functions
        for fragment in fragments.itertuples():
            intersection = fragment.geometry.intersection(cell.geometry)
            ai = intersection.area
            acmpl = fragment.geometry.area
            fragments_sum += ai * acmpl

        meff = fragments_sum / cell.geometry.area
        # convert to km2
        meff = meff / 1000**2
        mask.at[cell.Index, 'meff'] = meff

    return mask
