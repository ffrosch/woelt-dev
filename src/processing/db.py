import pandas as pd
import geopandas as gpd
import pyproj

from geoalchemy2 import Geometry, WKTElement
from shapely import wkt
from IPython.display import clear_output


def gdf_from_mssql(table, engine, geometry_column='geom', epsg=25832):

    geom = geometry_column
    sql = f'SELECT *, {geom}.STAsText() as geometry, {geom}.STSrid as srid FROM {table}'
    df = pd.read_sql(sql, engine)
    srid = df['srid'][0]
    df.drop(columns=[geom, 'srid'], inplace=True)
    df['geometry'] = df['geometry'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df)

    # if we can't determine the epsg code from the MSSQL Server we set it manually
    if srid == 0:
        gdf.crs = f'EPSG:{epsg}'
    else:
        gdf.crs = f'EPSG:{srid}'

    return gdf


def to_postgis(gdf, name, engine, epsg=3035, if_exists='fail',
               schema='processed', feature_type='POLYGON'):

    '''This function can be replaced by the new built-in function in geopandas >=0.8

    e.g.: gdf.to_postgis(name, engine, schema=None)'''

    # make sure the gdf will be in the desired CRS
    crs = pyproj.CRS(gdf.crs)
    crs = crs.to_epsg()
    if not crs == epsg:
        gdf.to_crs(epsg, inplace=True)

    # Convert Shapely Geometry to WKT and add the SRID
    gdf['geom'] = gdf['geometry'].apply(lambda x: WKTElement(x.wkt, srid=epsg))
    # convert column names to lowercase for easier querying
    gdf.columns = map(str.lower, gdf.columns)
    # drop the geometry column as it is now duplicative
    gdf.drop('geometry', 1, inplace=True)

    # set dtype to GeoAlchemy2's Geometry type
    try:
        gdf.to_sql(name, engine, schema=schema, if_exists=if_exists, index=False,
                   chunksize=10000, dtype={'geom': Geometry(feature_type, srid=epsg)})
        # clear the output in case the engine is run with echo=True
        clear_output()

    except ValueError as err:
        print(f'Dataset {name} could not be uploaded to PostGIS. Error: {err}')
        return False

    return True