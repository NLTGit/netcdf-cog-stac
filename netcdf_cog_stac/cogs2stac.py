import dateutil.parser
import logging
import pathlib

import pystac
from pystac import layout
import rasterio
from shapely.geometry import Polygon, mapping

from . import utils

LOG = logging.getLogger(__name__)


def cogs2stac(local_output_dir: pathlib.Path, final_output_path_or_url: str, base_name: str):
    LOG.info('Creating STAC files')
    cog_list = local_output_dir.glob(f'{base_name}_*.tiff')
    stac_items = [stac_item(path, final_output_path_or_url) for path in cog_list]
    collection = pystac.Collection(id=base_name,
                                   description=stac_items[0].properties['description'],
                                   extent=pystac.Extent.from_items(stac_items),
                                   catalog_type=pystac.CatalogType.SELF_CONTAINED)
    collection.add_items(stac_items)
    collection.normalize_hrefs(final_output_path_or_url,
                               strategy=single_folder_layout_strategy())
    collection.save(dest_href=str(local_output_dir))


def bbox_footprint_properties(path: pathlib.Path):
    with rasterio.open(path) as ds:
        bounds = ds.bounds
        bbox = [bounds.left, bounds.bottom, bounds.right, bounds.top]
        footprint = Polygon([
            [bounds.left, bounds.bottom],
            [bounds.left, bounds.top],
            [bounds.right, bounds.top],
            [bounds.right, bounds.bottom]
        ])

        return (bbox, mapping(footprint), ds.tags(1))


def stac_item(cog_path: pathlib.Path, final_output_path_or_url: str):
    id = cog_path.stem
    bbox, footprint, properties = bbox_footprint_properties(cog_path)
    # Use dateutil to recognize a datetime string of just "YYYY", which the
    # Python built-in datetime doesn't support
    item_datetime = dateutil.parser.isoparse(properties['datetime'])
    item = pystac.Item(id=id,
                       geometry=footprint,
                       bbox=bbox,
                       datetime=item_datetime,
                       properties=properties)
    image_href = utils.path_or_url_join(final_output_path_or_url, cog_path.name)
    item.add_asset(key='image',
                   asset=pystac.Asset(href=image_href, media_type=pystac.MediaType.COG))
    return item


def single_folder_layout_strategy():
    """Causes all STACs to be saved to the relative root directory instead of
    using STAC best practice layout"""
    collection_template = 'collection.json'
    item_template = '${id}.json'
    return layout.TemplateLayoutStrategy(
        collection_template=collection_template, item_template=item_template)
