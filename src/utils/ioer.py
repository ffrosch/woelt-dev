from pathlib import Path

import rasterio


def get_layers(wcs, resolutions=['500m', '1000m', '5000m', '10000m']):
    layers = []

    for layer in wcs.contents.keys():
        res = layer.split('_')[-1]
        if res in resolutions:
            layers.append(layer)

    return layers


def download_layers(wcs, layers, path='raw', skip_existing=True):
    print('Attempting to download the following layers:', layers)
    results = []

    for layer in layers:
        out_path = f'{path}/{layer}.tif'

        if skip_existing and Path(out_path).exists():
            print(f'Layer {layer} already exists. [Skipping]')
            results.append(out_path)
            continue

        print(f'Downloading {layer}...')
        dataset = wcs.contents[layer]
        bbox = dataset.boundingboxes[0]['bbox']
        crs = dataset.boundingboxes[0]['nativeSrs'].split('/')[-1]
        fmt = 'image/tiff'  # dataset.supportedFormats[0]

        img = wcs.getCoverage(identifier=[layer],
                              bbox=bbox,
                              crs=f'EPSG:{crs}',
                              format=fmt,
                              transparent=True,
                              nodata=0)

        with open(out_path, 'wb') as out:
            out.write(img.read())

        with rasterio.open(out_path, mode='r+') as r:
            r.crs = rasterio.crs.CRS.from_epsg(crs)

        results.append(out_path)

    print('---Successfully downloaded all layers---')
    return results
