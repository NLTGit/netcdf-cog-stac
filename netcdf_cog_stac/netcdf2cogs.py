import logging

from dateparser.search import search_dates
import dateutil.parser as parser
import dateutil.relativedelta as rd
from netCDF4 import Dataset
from osgeo import gdal

gdal.SetConfigOption('GDAL_PAM_ENABLED', 'NO')

LOG = logging.getLogger(__name__)


def netcdf2cogs(source_file, output_dir, base_name):
    LOG.info('Converting NetCDF file to COG files')
    netcdf_dataset = Dataset(source_file)
    dataset_time = netcdf_dataset['/time']

    gdal_file = gdal.Open(source_file)
    num_bands = gdal_file.RasterCount

    for num in range(1, num_bands + 1):
        band = gdal_file.GetRasterBand(num)
        band_time = band.GetMetadataItem('NETCDF_DIM_time')
        output_filename = f"{base_name}_{band_time}.tiff"
        full_output_filename = output_dir.joinpath(output_filename)
        band_datetime = get_band_datetime(dataset_time, band_time)

        metadata = base_metadata(netcdf_dataset)
        metadata['units'] = band.GetMetadataItem('units')
        metadata['title'] = base_name
        metadata['start_datetime'] = band_datetime
        metadata['end_datetime'] = band_datetime
        band.SetMetadata(metadata)

        gdal.Translate(str(full_output_filename), gdal_file,
                       bandList=[num], format='COG',
                       creationOptions=['COMPRESS=LZW', 'TARGET_SRS=WGS84',
                                        'NUM_THREADS=ALL_CPUS'])


def parse_date(date_string):
    """
    Does its best to parse the freeform strings provided in the NetCDF creation_date attribute
    for datetimes
    :param date_string: string to be searched for a datetime
    :return: list of dictionaries containing all datetime info found in string
    """
    dates = search_dates(date_string)
    if not dates:
        raise RuntimeError(f'Cannot parse date from: {date_string}')

    date_ranges = []
    for date in dates:
        # check if date found is just a year and add a new dict with just the year
        if str(date[1].year) == date[0]:
            date_ranges.append({"type": "year", "date": date[0]})
        # if it's not just a year, add a new dict with the date in iso format
        elif date[1].day:
            date_ranges.append({"type": "date", "date": date[1].isoformat()})
    return date_ranges


def get_created_and_updated(datetimes):
    """
    :param datetimes: list of datetime dictionaries found by parse_date
    :return: dictionary with datetime metadata formatted for STAC
    """
    if datetimes[0]['type'] in ('year', 'date') and len(datetimes) == 1:
        return {"datetime": datetimes[0]['date']}
    elif all(date['type'] in ('year', 'date') for date in datetimes) and len(datetimes) > 1:
        years = [date['date'] for date in datetimes]
        years.sort()
        return {"created": years[0], "updated": years[-1]}
    else:
        raise RuntimeError(f'Unrecognized parsed dates: {datetimes}')


def get_band_datetime(netcdf_time, delta):
    """
    Calculates the datetime specified for the raster band from NetCDF
    :param netcdf_time: NetCDF Dataset time variable
    :param delta: units of offset from origin datetime
    :return: ISO formatted datetime
    """
    unit = netcdf_time.units.split(' ')[0]
    origin = netcdf_time.time_origin
    origin_dt = parser.parse(origin)
    if unit == 'days':
        datetime_delta = origin_dt+rd.relativedelta(days=int(delta))
        datetime_iso = datetime_delta.isoformat()
        return datetime_iso
    elif unit == 'months':
        datetime_delta = origin_dt + rd.relativedelta(months=int(delta))
        datetime_iso = datetime_delta.isoformat()
        return datetime_iso
    elif unit == 'years':
        datetime_delta = origin_dt + rd.relativedelta(years=int(delta))
        datetime_iso = datetime_delta.isoformat()
        return datetime_iso


def base_metadata(netcdf_dataset):
    """
    Creates a dictionary of global metadata for all output files
    :param netcdf_dataset: NetCDF4 Dataset object
    :return: dictionary of metadata formatted for STAC
    """
    description = netcdf_dataset.getncattr('description')
    parsed_creation_date = parse_date(netcdf_dataset.getncattr('creation_date'))
    creation_date_dict = get_created_and_updated(parsed_creation_date)
    metadata = {'description': description}
    if creation_date_dict.get('datetime'):
        metadata['datetime'] = creation_date_dict.get('datetime')
    elif creation_date_dict.get('created') and creation_date_dict.get('updated'):
        metadata['created'] = creation_date_dict.get('created')
        metadata['updated'] = creation_date_dict.get('updated')
    return metadata
