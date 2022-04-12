import argparse
import contextlib
import ftplib
import logging
import os
import pathlib
import shutil
import re
from tempfile import TemporaryDirectory
import urllib.parse
import urllib.request

import boto3

from . import cogs2stac
from . import netcdf2cogs
from . import utils

LOG = logging.getLogger(__name__)


def main():
    args = parse_args()
    with automatic_or_custom_temp_dir(args) as temp_dir:
        LOG.info(f'Using temporary folder {temp_dir}')
        for source_filename in source_files(args.source, temp_dir):
            LOG.info(f'Converting {source_filename}')
            # Lowercase base_name since it becomes the STAC collection ID, and
            # stac-server creates an ElasticSearch index name based on the
            # collection ID. ElasticSearch index names must be lowercase.
            # https://github.com/stac-utils/stac-server/issues/110
            base_name = os.path.splitext(os.path.basename(source_filename))[0].lower()
            local_output_dir = temp_dir.joinpath(base_name)
            final_output_path_or_url = utils.path_or_url_join(args.destination, base_name)

            local_output_dir.mkdir(exist_ok=True)
            netcdf2cogs.netcdf2cogs(source_filename, local_output_dir, base_name)
            cogs2stac.cogs2stac(local_output_dir, final_output_path_or_url, base_name)
            copy_files_to_destination(local_output_dir, final_output_path_or_url)


def parse_args():
    parser = argparse.ArgumentParser(description='Convert NetCDF file(s) to COG and STAC')
    parser.add_argument('source',
                        help='''
                            Path to a file or directory to convert. Can be an FTP URL like
                            ftp://gdo-dcp.ucllnl.org/pub/dcp/archive/1950-2099/sresb1/sresb1.bccr_bcm2_0.1.monthly.Prcp.1950-2099.nc
                            If an FTP directory is specified by including a trailing slash (/),
                            all .nc files in that directory (non-recursively) will be converted.
                            Example: ftp://gdo-dcp.ucllnl.org/pub/dcp/archive/1950-2099/sresb1/
                        ''')
    parser.add_argument('destination',
                        help='A folder to save COGs and STACs to. '
                             'Can be an S3 URL like s3://bucketname/')
    parser.add_argument('-t', '--temp-dir',
                        help='A folder to save temporary files to.'
                             ' Will be created if it does not exist.'
                             ' WARNING: Overwrites existing files in the folder.',
                        type=pathlib.Path)
    parser.add_argument('-d', '--debug',
                        help='Print lots of debugging statements (implies --verbose)',
                        action='store_const', dest='log_level', const=logging.DEBUG,
                        default=logging.WARNING)
    parser.add_argument('-v', '--verbose',
                        help='Print more verbose logging statements (overrides --debug)',
                        action='store_const', dest='log_level', const=logging.INFO)
    args = parser.parse_args()

    parsed_destination_url = urllib.parse.urlparse(args.destination)
    if parsed_destination_url.scheme and parsed_destination_url.scheme.casefold() != 's3':
        parser.exit(message=f'Unable to handle non-S3 scheme: {parsed_destination_url.scheme}')
    logging.basicConfig(level=args.log_level)
    return args


@contextlib.contextmanager
def automatic_or_custom_temp_dir(args: argparse.Namespace):
    if args.temp_dir:
        args.temp_dir.mkdir(exist_ok=True)
        yield args.temp_dir
    else:
        with TemporaryDirectory(prefix=__name__) as temp_dir:
            yield pathlib.Path(temp_dir)


def source_files(path_or_url: str, temp_dir: pathlib.Path):
    parsed_url = urllib.parse.urlparse(path_or_url)
    if parsed_url.scheme:
        output_file_path = temp_dir.joinpath(os.path.basename(path_or_url))
        if parsed_url.scheme == 'ftp' and parsed_url.path.endswith('/') and parsed_url.hostname:
            with ftplib.FTP(host=parsed_url.hostname) as ftp:
                ftp.login()
                ftp.cwd(parsed_url.path)
                files_in_ftp_directory = ftp.nlst()
            for filename in files_in_ftp_directory:
                if not filename.endswith('.nc'):
                    continue
                # prevent a malicious remote filename from breaking out of our
                # local output directory if the remote filename contains a slash:
                sanitized_filename = re.sub(r'[^0-9a-zA-Z._-]', '_', filename)
                joined_output_file_path = output_file_path.joinpath(sanitized_filename)
                yield str(download_from_url(url=f'{path_or_url}{sanitized_filename}',
                                            output_file_path=joined_output_file_path))
        else:
            yield str(download_from_url(path_or_url, output_file_path))
    else:
        yield path_or_url


def download_from_url(url: str, output_file_path: pathlib.Path):
    LOG.info(f'Downloading {url} to {output_file_path}')
    with contextlib.closing(urllib.request.urlopen(url)) as url_reader:
        with output_file_path.open('wb') as f:
            shutil.copyfileobj(url_reader, f)
    return output_file_path


def copy_files_to_destination(local_dir: pathlib.Path, remote_path_or_url):
    parsed_url = urllib.parse.urlparse(remote_path_or_url)
    if parsed_url.scheme:
        bucket = boto3.resource('s3').Bucket(parsed_url.netloc)
        s3_base_path = parsed_url.path.lstrip('/')
        LOG.info(f'Uploading to s3://{parsed_url.netloc}/{s3_base_path}')
        for path in local_dir.iterdir():
            s3_object_name = '/'.join((s3_base_path, path.name))
            LOG.debug(f'Uploading {path} to {s3_object_name} as public-readable')
            bucket.upload_file(str(path), s3_object_name, ExtraArgs={'ACL': 'public-read'})
    else:
        shutil.copytree(local_dir, remote_path_or_url)


if __name__ == '__main__':
    main()
