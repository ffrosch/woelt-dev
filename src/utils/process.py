import pandas as pd


def merge_features(lst, ignore_duplicates=True, merge_on='cellcode'):

    lst = list(reversed(lst))

    if ignore_duplicates:
        cols_set_list = [set(df.columns) for df in lst]
        cols_common = set.intersection(*cols_set_list)
        cols_duplicate = cols_common - {merge_on}
    else:
        cols_duplicate = []

    gdf = lst.pop()

    while len(lst) > 0:
        gdf_append = lst.pop()
        gdf_append = gdf_append.drop(columns=cols_duplicate)
        gdf = pd.merge(gdf, gdf_append, on=merge_on)

    return gdf
