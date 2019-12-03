import argparse
import asyncio
import logging
import os
from functools import partial

import aiofiles
from aiohttp import web


async def archivate(request, delay, directory, chunk_byte_size=-10000):
    archive_dir = request.match_info['archive_hash']
    archive_path = os.path.join(directory, archive_dir)

    if not os.path.exists(archive_path):
        raise web.HTTPNotFound(
            text="Files not found. Archive doesn't exist or has been deleted."
        )

    cmd = ['zip', '-jr', '-', archive_path]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    response = web.StreamResponse()
    response.headers['Content-Disposition'] = f'attachment; filename="{archive_dir}.zip'
    await response.prepare(request)

    try:
        while True:
            archive_chunk = await process.stdout.read(chunk_byte_size)
            logging.debug('Sending archive chunk.')
            if not archive_chunk:
                break
            await response.write(archive_chunk)
            await asyncio.sleep(delay)
    except asyncio.CancelledError:
        logging.warning('Download was interrupted.')
        process.kill()
        raise
    finally:
        response.force_close()

    return response


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


def parser_args():
    parser = argparse.ArgumentParser(
        description='Create arhive from files and downloar it.'
    )
    parser.add_argument(
        '-V', '--verbose',
        action='store_true',
        help='Enable od disable error logging.'
    )
    parser.add_argument(
        '-D', '--directory',
        default='test_photos',
        help='Path to downloading files.'
    )
    parser.add_argument(
        '-d', '--delay',
        type=int,
        default=1,
        help='Delaying between archive chunks sending.'
    )

    return parser.parse_args()


def main():
    logging_level = logging.INFO
    arguments = parser_args()

    if arguments.verbose:
        logging_level = logging.DEBUG
    logging.basicConfig(level=logging_level, format='%(message)s')

    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', partial(archivate, delay=arguments.delay, directory=arguments.directory)),
    ])
    web.run_app(app)


if __name__ == '__main__':
    main()
