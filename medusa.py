#!/usr/bin/python3

# Medusa - Turn dynamic websites into static stones!
# Copyright (C) 2024 Sohrab Alimardani
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import re
from os import makedirs
from sys import exit
from datetime import datetime
from io import BytesIO
from urllib.parse import urlparse
from argparse import ArgumentParser
import pycurl

argparser = ArgumentParser(
    prog='medusa',
    description='Turn dynamic websites into static stones!',
)

argparser.add_argument('Root URL')
argparser.add_argument('-s', '--skip', nargs='*', help='skip paths that contain', action='append')
argparser.add_argument('--no-static', help='skip downloading static files', action='store_true')
argparser.add_argument('--absolute-url', nargs='?', help='prefix links with given URL', action='store', default=None)
argparser.add_argument('--no-ssl-verify', help="don't verify SSL cert of target URL", action='store_true')
argparser.add_argument('--socks-proxy-port', nargs='?', help='connect through socks5 proxy on given localhost port', action='store', default=None)
pargs = argparser.parse_args()
pargs = vars(pargs)
skip_list_input = []
ABSOLUTE_URL_PREFIX = ''

if pargs['skip']:
    skip_list_input = [ x for xs in pargs['skip'] for x in xs if x ]

if skip_list_input:
    print(f'Skipping paths that contain: {" ".join(skip_list_input)}')

if pargs['no_static']:
    print('Skipping downloading static assets')

if pargs['absolute_url']:
    ABSOLUTE_URL_PREFIX = re.sub('[/]+$', '', pargs['absolute_url'])
    print(f'Prefixing links with {ABSOLUTE_URL_PREFIX}')

input_link = pargs['Root URL']
parsed_uri = urlparse(input_link)
input_host = parsed_uri.netloc
scheme     = parsed_uri.scheme
output_dir = f'{parsed_uri.netloc}_files'
nginx_confs_output_dir = f'{parsed_uri.netloc}_nginx_confs'
input_root_url = f'{parsed_uri.scheme}://{parsed_uri.netloc}'
input_path = parsed_uri.path
input_url = f'{parsed_uri.scheme}://{parsed_uri.netloc}{parsed_uri.path}'

if input_path in {'', '/'}:
    start_at_root = True
else:
    start_at_root = False

RE_HREF                 = re.compile(r'''href=['"]?(\S+?)[\n"'#> ]''')
RE_SRC                  = re.compile(r'''src=['"]?(\S+?)[\n"'#> ]''')
RE_ALL_LINKS            = re.compile(r'''(src|href)=(['"])?https?://''' + input_host + '[/]?')
RE_ALL_LINKS_SCHEMELESS = re.compile(r'''(src|href)=(['"])?//''' + input_host + '/')
RE_CSS_URLS_FULL_CLEAN  = re.compile(r'''url\((['"])?https?://''' + input_host + '/')
RE_CSS_URLS_ALL         = re.compile(r'''url\((['"])?([^ '"?)#]+)''')
RE_INLINE_STYLE         = re.compile(r'''<style(.+?)(?:</style>|/>)''', flags=re.DOTALL)

c = pycurl.Curl()
c.setopt(pycurl.USERAGENT, "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
c.setopt(pycurl.FOLLOWLOCATION, 1)
c.setopt(pycurl.HTTPHEADER, ['ACCEPT: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
'ACCEPT_ENCODING: gzip, deflate, br','ACCEPT_LANGUAGE: en-US,en;q=0.5','CONNECTION: keep-alive',
'UPGRADE_INSECURE_REQUESTS: 1','DNT: 1',])

if pargs['socks_proxy_port']:
    try:
        socks_proxy_port = int(pargs['socks_proxy_port'])
    except:
        print('Argument to --socks-proxy-port must be of integer type')
        exit(1)
    c.setopt(pycurl.PROXY, '127.0.0.1')
    c.setopt(pycurl.PROXYPORT, socks_proxy_port)
    c.setopt(pycurl.PROXYTYPE, pycurl.PROXYTYPE_SOCKS5_HOSTNAME)

if pargs['no_ssl_verify']:
    c.setopt(pycurl.SSL_VERIFYPEER, 0)
    c.setopt(pycurl.SSL_VERIFYHOST, 0)

link_to_file = {}
dirs_to_create = {}
written_htmls = {}
static_assets = set()
css_files = set()
css_assets = set()
skipped_urls = set()

STATIC_EXTENSIONS = ('.js', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp',
    '.bmp', '.avif', '.json', '.woff', '.woff2', '.ttf', '.mp4',
)

def get_html_and_links(link):
    buffer = BytesIO()
    c.setopt(c.URL, bytes(link, 'utf-8'))
    c.setopt(c.WRITEDATA, buffer)
    try:
        c.perform()
    except Exception as e:
        print(f'Encountered error while downloading {link}: {e}')
        return (None, None, None)
    if not (c.getinfo(pycurl.RESPONSE_CODE) >= 200 and c.getinfo(pycurl.RESPONSE_CODE) < 400):
        return (None, None, None)
    html = buffer.getvalue().decode('utf-8' , 'ignore')

    href_links_list = RE_HREF.findall(html)
    src_links_list  = RE_SRC.findall(html)

    current_path_dir = '/'.join(link.replace(input_root_url, '').split('/')[:-1])

    hrefs_set = resolve_links(href_links_list, current_path_dir)
    srcs_set  = resolve_links(src_links_list,  current_path_dir)

    inline_style_sections = RE_INLINE_STYLE.findall(html)
    for style_section in inline_style_sections:
        modified_style_section = process_css_url_functions(link, style_section)
        html = html.replace(style_section, modified_style_section)

    all_links = []
    all_links.extend(hrefs_set)
    all_links.extend(srcs_set)

    for link in all_links:
        if link.lower().endswith(STATIC_EXTENSIONS):
            static_assets.add(link)
        elif link.endswith('.css'):
            css_files.add(link)
        elif '.css?' in link:
            css_files.add(link[:link.find('?')])
        elif '.js?' in link:
            static_assets.add(link[:link.find('?')])

    non_asset_links = hrefs_set - static_assets - css_files
    non_asset_links = {x for x in non_asset_links if input_url in x}
    non_asset_links = {x for x in non_asset_links if '.css?' not in x and '.js?' not in x}

    return (html, non_asset_links, current_path_dir)

def resolve_links(links, current_path_dir):
    output = set()

    for link in links:
        if link.startswith(f'{scheme}://{input_host}'):
            complete_link = link
        elif link.startswith('http') and not link.startswith(f'{scheme}://{input_host}'):
            continue
        elif link.startswith('/') and not link.startswith('//'):
            complete_link = f'{input_root_url}{link}'
        elif link.startswith(f'//{input_host}'):
            complete_link = f'{scheme}:{link}'
        elif link.startswith('./'):
            complete_link = f'{input_root_url}{current_path_dir}{link[1:]}'
        elif link.startswith('../'):
            ls = link.split('../')
            levels = len(ls) - 1
            current_path_dirs = current_path_dir.split('/')
            if levels >= len(current_path_dirs):
                complete_link = f'{input_root_url}/{ls[-1]}'
            else:
                dir = '/'.join(current_path_dirs[:-levels])
                complete_link = f'{input_root_url}{dir}/{ls[-1]}'
        elif link.startswith('#'):
            continue
        elif link.startswith('data:'):
            continue
        elif link:
            complete_link = f'{input_root_url}{current_path_dir}/{link}'

        output.add(complete_link)

    return output

def create_directories(links):
    for link in links:
        path_and_name = link.replace(f'{input_root_url}/', '')
        path_and_name = '/'.join(path_and_name.split('/')[:-1])
        path_and_name = f'{output_dir}/{path_and_name}'
        dirs_to_create[path_and_name] = False

    for path in dirs_to_create:
        if dirs_to_create[path] == False:
            makedirs(path, exist_ok=True)
            dirs_to_create[path] = True

def download_assets(links):
    for link in links:
        c.setopt(c.URL, bytes(link, 'utf-8'))
        path_and_name = link.replace(f'{input_root_url}/', '')
        filename = f'{output_dir}/{path_and_name}'
        c.fp = open(filename, "wb")
        c.setopt(c.WRITEDATA, c.fp)
        try:
            c.perform()
        except Exception as e:
            print(f'Encountered error while downloading {link}: {e}')
            continue

def write_html_file(html, name):
    html = RE_ALL_LINKS.sub(fr'\1=\2{ABSOLUTE_URL_PREFIX}/', html)
    html = RE_ALL_LINKS_SCHEMELESS.sub(fr'\1=\2{ABSOLUTE_URL_PREFIX}/', html)

    with open(f'{output_dir}/{name}.html', 'w') as f:
        f.writelines(html)

def process_css_url_functions(link, content):
    current_css_path = '/'.join(link.replace(input_root_url, '').split('/')[:-1])

    css_asset_links = RE_CSS_URLS_ALL.findall(content)
    css_asset_links = [x[1] for x in css_asset_links]
    css_asset_links = resolve_links(css_asset_links, current_css_path)

    for css_link in css_asset_links:
        if css_link.endswith(STATIC_EXTENSIONS):
            css_assets.add(css_link)

    modified_content = RE_CSS_URLS_FULL_CLEAN.sub(r'url(\1/', content)
    return modified_content

def download_css_files(css_files):
    for link in css_files:
        buffer = BytesIO()
        c.setopt(c.URL, bytes(link, 'utf-8'))
        c.setopt(c.WRITEDATA, buffer)
        try:
            c.perform()
        except Exception as e:
            print(f'Encountered error while downloading {link}: {e}')
            continue
        if not (c.getinfo(pycurl.RESPONSE_CODE) >= 200 and c.getinfo(pycurl.RESPONSE_CODE) < 400):
            continue
        css = buffer.getvalue().decode('utf-8' , 'ignore')

        css = process_css_url_functions(link, css)

        path_and_name = link.replace(f'{input_root_url}/', '')
        css_filename = f'{output_dir}/{path_and_name}'

        with open(css_filename, 'w') as f:
            f.writelines(css)


print('Getting the inital page...')

makedirs(output_dir, exist_ok=True)

html, non_asset_links, current_path_dir = get_html_and_links(input_link)

if not html:
    print('Getting the initial page failed. Exiting.')
    exit(1)

if start_at_root:
    write_html_file(html, 'index')
    written_htmls[hash(html)] = 'index'
else:
    filename = input_path.replace('/', '-')
    write_html_file(html, filename)
    written_htmls[hash(html)] = filename
    link_to_file[input_url] = filename

while True:
    try:
        link = non_asset_links.pop()
    except:
        break

    if link in link_to_file or link in skipped_urls:
        continue

    skip = False
    if skip_list_input:
        for skip_str in skip_list_input:
            if skip_str in link:
                skipped_urls.add(link)
                skip = True
        if skip:
            continue

    print(f'Getting {link}...')
    html, non_asset_links_i, current_path_dir = get_html_and_links(link)

    if not html:
        continue

    non_asset_links.update(non_asset_links_i)

    html_hash = hash(html)

    if html_hash in written_htmls:
        filename = written_htmls[html_hash]
    else:
        filename = link.replace(f'{input_root_url}/', '').replace('/', '-')
        write_html_file(html, filename)
        written_htmls[html_hash] = filename

    link_to_file[link] = filename

print('Downloading CSS files...')
create_directories(css_files)
download_css_files(css_files)

if pargs['no_static'] == False:
    print('Downloading static assets...')
    create_directories(static_assets)
    download_assets(static_assets)

    print('Downloading CSS static assets...')
    create_directories(css_assets)
    download_assets(css_assets)

print('Writing Nginx configuration files...')

makedirs(nginx_confs_output_dir, exist_ok=True)

with open(f'{nginx_confs_output_dir}/url_paths.conf', 'w') as f:
    for link in link_to_file:
        link_path = link.replace(f'{input_root_url}', '')
        f.write(f'location = {link_path} {{ try_files /{link_to_file[link]}.html =404; }}\n')

current_datetime = datetime.now().strftime("%Y-%m-%dT%H-%M")

print('\nAll done!')
print('Run the following command to build the docker image:\n')
print(f'docker build --build-arg WEBROOT_DIR={output_dir} --build-arg NGINX_CONFS_DIR={nginx_confs_output_dir} -t {input_host}-static-website:{current_datetime} .\n')
