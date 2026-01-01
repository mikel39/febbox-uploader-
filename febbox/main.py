import asyncio
import gc
from hashlib import md5
from pathlib import Path

import httpx
from rich.console import Console
from rich.markup import escape
from rich.progress import Progress

from .utils import chunk_hash, get_file_hash, get_files

console = Console()


class Febbox:
    def __init__(self, token: str, rm: bool) -> None:
        self.clt = httpx.AsyncClient(
            cookies={'ui': token},
            headers={
                'user-agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0',
            },
            timeout=60.0,
            transport=httpx.AsyncHTTPTransport(retries=10),
        )
        self.rm = rm

    async def init_file_upload(self, fl_path: Path, hash: str, rm_ph):
        data = {
            'name': fl_path.name,
            'size': fl_path.stat().st_size,
            'hash': hash,
            'path': rm_ph,
            'last_time': int(fl_path.stat().st_mtime * 1000),
        }

        res = await self.clt.post(
            'https://www.febbox.com/console/file_upload?parent_id=0&from_uid=&fid=',
            data=data,
        )

        nm = escape(data['name'])

        if res.status_code == 500:
            console.log(
                f'[red bold]Token could be wrong or file already uploaded ah well {nm}'
            )
            return

        res = res.json()

        if res['code'] != 1:
            console.log(f'[bold red]Failed to init upload: {nm}')
            console.print(res)
            return

        console.log(f'[blue]Initiatinn upload: {nm}')

        return res

    async def init_chunk_upload(self, fl_path: Path, ck_data, fl_hash, chunk, nck):
        size = fl_path.stat().st_size

        if size < 52428800:
            hash = md5(chunk).hexdigest()
        else:
            hash = chunk_hash(chunk)

        data = {
            'chunk_data': ck_data,
            'file_name': fl_path.name,
            'file_size': size,
            'file_hash': fl_hash,
            'chunk_hash': hash,
            'chunk_size2': str(len(chunk)),
        }

        res = await self.clt.post(
            f'https://www.febbox.com/console/file_upload_chunk2?chunk={nck}',
            data=data,
        )

        res = res.json()

        return res

    async def upload_chunk(self, url, ck_dt, chunk):
        res = await self.clt.post(url, data={'data': ck_dt}, files={'file': chunk})
        res = res.json()

        if res['code'] != 1:
            console.log('[bold red]Failed while uploading')
            console.print(res)
            return

        return res, len(chunk)

    async def final_upload(self, fl_data, fid, path: Path, rm_ph):
        data = {
            'file_data': fl_data,
            'oss_fid': fid,
            'path': rm_ph,
            'last_time': int(path.stat().st_mtime * 1000),
        }

        res = await self.clt.post(
            'https://www.febbox.com/console/file_add?parent_id=0&from_uid=&fid=',
            data=data,
            headers={
                'X-Requested-With': 'XMLHttpRequest',
            },
        )

        res = res.json()

        if res['code'] != 1:
            console.log('[bold red] Failes to upload')
            console.print(res)
            return

        return res

    async def upload_file(self, pt, rm_path=''):
        path = Path(pt)

        file_hash = get_file_hash(path)

        init_up = await self.init_file_upload(path, file_hash, rm_path)

        if not init_up:
            return

        up_data = init_up['data']

        with open(path, 'rb') as f:
            nt_up = up_data['not_upload']
            ck_size = up_data['chunk_size']
            point = f.seek(ck_size * nt_up[0])
            fl_data = ''
            fid = 0

            progress = Progress(expand=True, transient=True)
            progress.start()
            bar = progress.add_task(
                '[red]Uploading...', total=path.stat().st_size - point
            )

            tasks = []

            for nck in nt_up:
                chunk = f.read(ck_size)

                init_cu = await self.init_chunk_upload(
                    path, up_data['chunk_data'], file_hash, chunk, nck
                )
                fl_data = init_cu['file_data']

                uc = self.upload_chunk(init_cu['api_chunk'], init_cu['api_data'], chunk)

                if not (uc):
                    return

                tasks.append(uc)

                if len(tasks) >= 3 or nck == nt_up[-1]:
                    tsks = await asyncio.gather(*tasks)
                    tasks.clear()

                    total = 0
                    for t in tsks:
                        total += t[1]

                        if t[0]['data']:
                            fid = t[0]['data']['oss_fid']
                    progress.update(bar, advance=total)
                    gc.collect()

            final = await self.final_upload(fl_data, fid, path, rm_path)
            progress.stop()

            if not final:
                return

            console.log('[bold green]Succefully uploaded!')

            if self.rm:
                path.unlink()

            return final

    async def upload_folder(self, folder, rm_path=''):
        files = get_files(folder)
        root = Path(folder)

        for file in files:
            path = Path(file)
            rm_pth = path.relative_to(root)
            rm_pth = Path(rm_path, root.name, rm_pth.parent)
            await self.upload_file(file, str(rm_pth) + '/')
